from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class RegistrationTests(APITestCase):
    url = '/api/users/register/'
    username = 'egor'
    password = 'HelloWorld!'

    def test_registers_user_with_hashed_password(self):
        response = self.client.post(
            self.url,
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
            self.url,
            {'username': self.username, 'password': self.password},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_weak_password(self):
        response = self.client.post(
            self.url,
            {'username': self.username, 'password': '123'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
