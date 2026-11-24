from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from .serializers import OrderSerializer
from .services import checkout


class CheckoutView(GenericAPIView):
    serializer_class = OrderSerializer

    @extend_schema(
        request=None,
        responses={status.HTTP_201_CREATED: OrderSerializer},
        description='Оформляет текущую корзину покупателя.',
    )
    def post(self, request):
        order = checkout(request.user)
        return Response(
            self.get_serializer(order).data, status=status.HTTP_201_CREATED
        )
