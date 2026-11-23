from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import CartItem
from .serializers import AddCartItemSerializer, CartItemSerializer, UpdateCartItemSerializer
from .services import add_cart_item, cart_write_transaction


class CartViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = CartItemSerializer

    def get_queryset(self):
        return (
            CartItem.objects.filter(user_id=self.request.user.pk)
            .select_related('product')
            .order_by('pk')
        )

    def create(self, request, *args, **kwargs):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with cart_write_transaction(request.user):
            item, created = add_cart_item(request.user, **serializer.validated_data)
            data = self.get_serializer(item).data

        response_status = (status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        return Response(data, status=response_status)

    def partial_update(self, request, *args, **kwargs):
        with cart_write_transaction(request.user):
            item = self.get_object()
            serializer = UpdateCartItemSerializer(item, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            data = self.get_serializer(item).data

        return Response(data)

    def destroy(self, request, *args, **kwargs):
        with cart_write_transaction(request.user):
            return super().destroy(request, *args, **kwargs)
