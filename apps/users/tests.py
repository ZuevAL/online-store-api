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


class BalanceTopUpTests(APITestCase):
    def setUp(self):
        self.url = reverse('users:top_up')
        self.user = get_user_model().objects.create_user(
            username='buyer', balance=Decimal('20.00')
        )
        access_token = AccessToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

    def test_adds_amount_to_token_owners_balance(self):
        other_user = get_user_model().objects.create_user(
            username='other_user', balance=Decimal('42.00')
        )

        response = self.client.post(
            self.url, {'amount': '5.50'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'balance': '25.50'})
        self.user.refresh_from_db()
        other_user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('25.50'))
        self.assertEqual(other_user.balance, Decimal('42.00'))

    def test_rejects_invalid_amounts(self):
        invalid_payloads = (
            {},
            {'amount': '0'},
            {'amount': '-1'},
            {'amount': '0.001'},
            {'amount': 'invalid'},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format='json')

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )
                self.assertIn('amount', response.data)

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('20.00'))

    def test_enforces_maximum_balance(self):
        self.user.balance = Decimal('9999999999.98')
        self.user.save(update_fields=['balance'])

        payload = {'amount': '0.01'}
        at_limit = self.client.post(self.url, payload, format='json')
        over_limit = self.client.post(self.url, payload, format='json')

        self.assertEqual(at_limit.status_code, status.HTTP_200_OK)
        self.assertEqual(at_limit.data, {'balance': '9999999999.99'})
        self.assertEqual(over_limit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', over_limit.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('9999999999.99'))

    def test_requires_authentication(self):
        self.client.credentials()

        response = self.client.post(
            self.url, {'amount': '5.50'}, format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance, Decimal('20.00'))
