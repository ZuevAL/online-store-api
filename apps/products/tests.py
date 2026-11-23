from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import Product


class ProductAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            name='Notebook',
            description='Lined notebook',
            price=Decimal('12.50'),
            stock=5,
        )
        users = get_user_model().objects
        cls.customer = users.create_user(username='customer')
        cls.staff_user = users.create_user(username='staff', is_staff=True)

    def setUp(self):
        self.list_url = reverse('products:list')
        self.detail_url = reverse(
            'products:detail', kwargs={'pk': self.product.pk}
        )
        self.product_data = {
            'name': 'Pen',
            'description': 'Blue ink pen',
            'price': '2.75',
            'stock': 0,
        }

    def authenticate_as(self, user):
        access_token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_lists_products_without_authentication(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{
            'id': self.product.pk,
            'name': 'Notebook',
            'description': 'Lined notebook',
            'price': '12.50',
            'stock': 5,
        }])

    def test_requires_authentication_to_create_product(self):
        response = self.client.post(
            self.list_url, self.product_data, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_forbids_product_writes_for_regular_user(self):
        self.authenticate_as(self.customer)

        create = self.client.post(
            self.list_url, self.product_data, format='json'
        )
        update = self.client.patch(
            self.detail_url, {'stock': 9}, format='json'
        )
        delete = self.client.delete(self.detail_url)

        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(Product.objects.count(), 1)

    def test_staff_can_create_update_and_delete_product(self):
        self.authenticate_as(self.staff_user)

        create = self.client.post(
            self.list_url, self.product_data, format='json'
        )

        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(pk=create.data['id'])
        self.assertEqual(product.price, Decimal('2.75'))
        self.assertEqual(product.stock, 0)
        detail_url = reverse('products:detail', kwargs={'pk': product.pk})

        update = self.client.patch(detail_url, {'stock': 9}, format='json')

        self.assertEqual(update.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        self.assertEqual(product.stock, 9)

        delete = self.client.delete(detail_url)

        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_rejects_negative_price_or_stock(self):
        self.authenticate_as(self.staff_user)

        for field, value in [('price', '-0.01'), ('stock', -1)]:
            with self.subTest(field=field):
                response = self.client.post(
                    self.list_url,
                    {**self.product_data, field: value},
                    format='json',
                )

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn(field, response.data)
