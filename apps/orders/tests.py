from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import skipUnlessDBFeature
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.cart.models import CartItem
from apps.products.models import Product

from .models import Order


class CheckoutTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = get_user_model().objects.create_user(
            username='buyer', balance=Decimal('50.00')
        )
        cls.notebook = Product.objects.create(
            name='Notebook', description='Lined notebook',
            price=Decimal('12.50'), stock=5,
        )
        cls.pen = Product.objects.create(
            name='Pen', description='Blue ink pen',
            price=Decimal('3.25'), stock=7,
        )

    def setUp(self):
        self.url = reverse('orders:checkout')
        access_token = AccessToken.for_user(self.buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_checkout_saves_order_debits_stock_and_empties_cart(self):
        CartItem.objects.bulk_create([
            CartItem(user=self.buyer, product=self.notebook, quantity=2),
            CartItem(user=self.buyer, product=self.pen, quantity=3),
        ])

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(user=self.buyer)
        self.assertEqual(response.data, {'id': order.pk, 'total': '34.75'})
        self.assertCountEqual(
            order.items.values_list('product_name', 'unit_price', 'quantity'),
            [('Notebook', Decimal('12.50'), 2), ('Pen', Decimal('3.25'), 3)],
        )
        profile = self.client.get(reverse('users:profile'))
        catalog = self.client.get(reverse('products:list'))
        cart = self.client.get(reverse('cart:detail'))

        self.assertEqual(profile.data['balance'], '15.25')
        self.assertEqual(
            {product['id']: product['stock'] for product in catalog.data},
            {self.notebook.pk: 3, self.pen.pk: 4},
        )
        self.assertEqual(cart.data, [])

    def test_rejects_empty_cart(self):
        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())

    def test_rejects_insufficient_stock_and_preserves_cart(self):
        CartItem.objects.bulk_create([
            CartItem(user=self.buyer, product=self.notebook, quantity=1),
            CartItem(user=self.buyer, product=self.pen, quantity=8),
        ])

        self.assert_checkout_rejected()

    def test_rejects_insufficient_balance_and_preserves_cart(self):
        CartItem.objects.create(
            user=self.buyer, product=self.notebook, quantity=5
        )

        self.assert_checkout_rejected()

    def test_logs_order_only_on_commit(self):
        CartItem.objects.create(
            user=self.buyer, product=self.notebook, quantity=1
        )

        with self.assertLogs('apps.orders', level='INFO') as logs:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, format='json')
                self.assertEqual(logs.records, [])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn(f'Order {response.data["id"]} created', logs.output[0])

    def test_requires_authentication(self):
        self.client.credentials()

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def assert_checkout_rejected(self):
        profile_url = reverse('users:profile')
        cart_url = reverse('cart:detail')
        profile_before = self.client.get(profile_url).data
        cart_before = self.client.get(cart_url).data

        response = self.client.post(self.url, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(profile_url).data, profile_before)
        self.assertEqual(self.client.get(cart_url).data, cart_before)
        self.assertFalse(Order.objects.filter(user=self.buyer).exists())


@skipUnlessDBFeature('has_select_for_update')
class ConcurrentCheckoutTests(APITransactionTestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            username='buyer', balance=Decimal('30.00')
        )
        self.product = Product.objects.create(
            name='Notebook', description='Lined notebook',
            price=Decimal('7.50'), stock=5,
        )
        CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=2
        )

    def test_two_checkouts_of_same_cart_charge_once(self):
        statuses = self.checkout_concurrently(self.buyer, self.buyer)

        self.assertCountEqual(statuses, [201, 400])
        self.assertEqual(Order.objects.filter(user=self.buyer).count(), 1)
        self.buyer.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.buyer.balance, Decimal('15.00'))
        self.assertEqual(self.product.stock, 3)
        self.assertFalse(CartItem.objects.filter(user=self.buyer).exists())

    def test_two_buyers_cannot_purchase_same_remaining_stock(self):
        self.product.stock = 2
        self.product.save(update_fields=['stock'])
        other_buyer = get_user_model().objects.create_user(
            username='other_buyer', balance=Decimal('30.00')
        )
        CartItem.objects.create(
            user=other_buyer, product=self.product, quantity=2
        )

        statuses = self.checkout_concurrently(self.buyer, other_buyer)

        self.assertCountEqual(statuses, [201, 400])
        order = Order.objects.get()
        remaining_cart = CartItem.objects.get()
        self.assertNotEqual(order.user_id, remaining_cart.user_id)
        self.assertEqual(order.user.balance, Decimal('15.00'))
        self.assertEqual(remaining_cart.user.balance, Decimal('30.00'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def checkout_concurrently(self, *buyers):
        url = reverse('orders:checkout')
        tokens = [str(AccessToken.for_user(buyer)) for buyer in buyers]
        barrier = Barrier(len(tokens))

        def post_order(token):
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            try:
                barrier.wait(timeout=10)
                return client.post(url, format='json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(tokens)) as executor:
            return list(executor.map(post_order, tokens, timeout=20))
