from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError

from apps.products.models import Product

from .models import MAX_QUANTITY, CartItem


@contextmanager
def cart_write_transaction(user):
    with transaction.atomic():
        yield get_user_model().objects.select_for_update().get(pk=user.pk)


def add_cart_item(user, product, quantity):
    try:
        product = Product.objects.select_for_update().get(pk=product.pk)
    except Product.DoesNotExist as exc:
        raise ValidationError({'product': 'Товар не найден.'}) from exc

    item, created = CartItem.objects.get_or_create(user=user, product=product, defaults={'quantity': quantity})
    if created:
        return item, True

    updated = CartItem.objects.filter(
        pk=item.pk, quantity__lte=MAX_QUANTITY - quantity
    ).update(quantity=F('quantity') + quantity)
    if not updated:
        raise ValidationError({'quantity': 'Превышено максимальное количество.'})
    item.refresh_from_db(fields=['quantity'])
    return item, False
