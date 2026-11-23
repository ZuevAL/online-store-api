from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from apps.products.models import Product

from .models import MAX_QUANTITY, CartItem


class CartAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.buyer = users.create_user(username='buyer')
        cls.other_buyer = users.create_user(username='other_buyer')
        cls.product = Product.objects.create(
            name='Pen', description='Blue ink pen',
            price=Decimal('2.75'), stock=0,
        )

    def setUp(self):
        self.cart_url = reverse('cart:detail')
        self.add_url = reverse('cart:item_create')
        access_token = AccessToken.for_user(self.buyer)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_lists_only_current_users_cart_items(self):
        CartItem.objects.create(
            user=self.other_buyer, product=self.product, quantity=7
        )

        empty_cart = self.client.get(self.cart_url)

        self.assertEqual(empty_cart.status_code, status.HTTP_200_OK)
        self.assertEqual(empty_cart.data, [])
        own_item = CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=2
        )

        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{
            'id': own_item.pk,
            'product': {
                'id': self.product.pk,
                'name': 'Pen',
                'description': 'Blue ink pen',
                'price': '2.75',
                'stock': 0,
            },
            'quantity': 2,
        }])

    def test_adding_same_product_increases_quantity_of_one_item(self):
        first = self.client.post(
            self.add_url, {'product': self.product.pk, 'quantity': 2},
            format='json',
        )
        second = self.client.post(
            self.add_url, {'product': self.product.pk, 'quantity': 3},
            format='json',
        )

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data['quantity'], 2)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data['id'], first.data['id'])
        self.assertEqual(second.data['quantity'], 5)
        item = CartItem.objects.get(user=self.buyer, product=self.product)
        self.assertEqual(item.quantity, 5)

    def test_replaces_quantity_of_own_item(self):
        item = CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=2
        )
        url = reverse('cart:item_detail', kwargs={'pk': item.pk})

        response = self.client.patch(url, {'quantity': 5}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity'], 5)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 5)

    def test_deletes_own_item(self):
        item = CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=2
        )
        url = reverse('cart:item_detail', kwargs={'pk': item.pk})

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_other_users_item_returns_not_found(self):
        item = CartItem.objects.create(
            user=self.other_buyer, product=self.product, quantity=2
        )
        url = reverse('cart:item_detail', kwargs={'pk': item.pk})

        update = self.client.patch(url, {'quantity': 5}, format='json')
        delete = self.client.delete(url)

        self.assertEqual(update.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete.status_code, status.HTTP_404_NOT_FOUND)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_rejects_non_positive_quantities(self):
        item = CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=2
        )
        url = reverse('cart:item_detail', kwargs={'pk': item.pk})

        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                add = self.client.post(
                    self.add_url,
                    {'product': self.product.pk, 'quantity': quantity},
                    format='json',
                )
                update = self.client.patch(
                    url, {'quantity': quantity}, format='json'
                )

                self.assertEqual(add.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(
                    update.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn('quantity', add.data)
                self.assertIn('quantity', update.data)

        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_rejects_addition_beyond_maximum_quantity(self):
        item = CartItem.objects.create(
            user=self.buyer, product=self.product, quantity=MAX_QUANTITY
        )

        response = self.client.post(
            self.add_url, {'product': self.product.pk, 'quantity': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)
        item.refresh_from_db()
        self.assertEqual(item.quantity, MAX_QUANTITY)

    def test_rejects_unknown_product(self):
        response = self.client.post(
            self.add_url, {'product': self.product.pk + 1, 'quantity': 1},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('product', response.data)

    def test_requires_authentication(self):
        self.client.credentials()

        cart = self.client.get(self.cart_url)
        add = self.client.post(
            self.add_url, {'product': self.product.pk, 'quantity': 1},
            format='json',
        )

        self.assertEqual(cart.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(add.status_code, status.HTTP_401_UNAUTHORIZED)
