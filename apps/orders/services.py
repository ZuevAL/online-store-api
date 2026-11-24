import logging
from decimal import Decimal

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.cart.models import CartItem
from apps.cart.services import cart_write_transaction
from apps.products.models import Product

from .models import Order, OrderItem


logger = logging.getLogger(__name__)


def checkout(user):
    with cart_write_transaction(user) as buyer:
        cart_items = list(CartItem.objects.filter(user=buyer))
        if not cart_items:
            raise ValidationError({'detail': 'Корзина пуста.'})

        products = {
            product.pk: product
            for product in Product.objects.select_for_update().filter(
                pk__in=[item.product_id for item in cart_items]
            ).order_by('pk')
        }

        total = Decimal('0.00')
        order_items = []
        for item in cart_items:
            product = products.get(item.product_id)
            if product is None or product.stock < item.quantity:
                raise ValidationError({'detail': 'Недостаточно товара на складе.'})
            total += product.price * item.quantity
            order_items.append(OrderItem(product_name=product.name, unit_price=product.price, quantity=item.quantity))
            product.stock -= item.quantity

        if buyer.balance < total:
            raise ValidationError({'detail': 'Недостаточно средств на балансе.'})

        order = Order.objects.create(user=buyer, total=total)
        for item in order_items:
            item.order = order
        OrderItem.objects.bulk_create(order_items)

        buyer.balance -= total
        buyer.save(update_fields=['balance'])
        Product.objects.bulk_update(products.values(), ['stock'])
        CartItem.objects.filter(pk__in=[item.pk for item in cart_items]).delete()
        transaction.on_commit(
            lambda: logger.info('Order %s created', order.pk)
        )
        return order
