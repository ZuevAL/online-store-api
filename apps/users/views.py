from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.db.models.functions import Round
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import RegisterSerializer, TopUpSerializer, UserSerializer


MAX_BALANCE = Decimal('9999999999.99')


class RegisterView(CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class UserProfileView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class TopUpView(APIView):
    @extend_schema(
        request=TopUpSerializer,
        responses={
            status.HTTP_200_OK: inline_serializer(
                name='BalanceResponse',
                fields={
                    'balance': serializers.DecimalField(
                        max_digits=12, decimal_places=2
                    ),
                },
            ),
        },
    )
    def post(self, request):
        serializer = TopUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        amount = serializer.validated_data['amount']
        user = request.user

        with transaction.atomic():
            updated = User.objects.filter(
                pk=user.pk, balance__lte=MAX_BALANCE - amount,
            ).update(balance=Round(F('balance') + amount, precision=2))
            if not updated:
                raise ValidationError({
                    'amount': 'Пополнение превышает максимальный баланс.',
                })
            user.refresh_from_db(fields=['balance'])

        return Response({'balance': f'{user.balance:.2f}'})
