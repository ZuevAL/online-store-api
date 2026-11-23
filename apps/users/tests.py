from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken


class RegistrationTests(APITestCase):
    url_name = 'users:register'
    username = 'egor'
    password = 'HelloWorld!'

    def test_registers_user_with_hashed_password(self):
        response = self.client.post(
            reverse(self.url_name),
            {'username': self.username, 'password': self.password},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = get_user_model().objects.get(username=self.username)
        self.assertEqual(
            response.data, {'id': user.pk, 'username': self.username}
        )
        self.assertTrue(user.check_password(self.password))

    def test_rejects_duplicate_username(self):
        get_user_model().objects.create_user(
            username=self.username,
            password=self.password,
        )

        response = self.client.post(
            reverse(self.url_name),
            {'username': self.username, 'password': self.password},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_weak_password(self):
        response = self.client.post(
            reverse(self.url_name),
            {'username': self.username, 'password': '123'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)


class UserProfileTests(APITestCase):
    url_name = 'users:profile'

    def test_returns_profile_of_token_owner(self):
        users = get_user_model().objects
        users.create_user(username='other_user', balance=Decimal('10.00'))
        user = users.create_user(username='buyer', balance=Decimal('42.50'))
        access_token = AccessToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data, {'username': user.username, 'balance': '42.50'}
        )

    def test_requires_authentication(self):
        response = self.client.get(reverse(self.url_name))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
