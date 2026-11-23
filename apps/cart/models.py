from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


MAX_QUANTITY = 2_147_483_647


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(MAX_QUANTITY)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('user', 'product'), name='unique_cart_user_product'),
            models.CheckConstraint(condition=models.Q(quantity__range=(1, MAX_QUANTITY)),
                                   name='cart_item_quantity_in_range'),
        ]
