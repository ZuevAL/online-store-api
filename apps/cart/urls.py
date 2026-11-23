from django.urls import path

from .views import CartViewSet


app_name = 'cart'

urlpatterns = [
    path('', CartViewSet.as_view({'get': 'list'}), name='detail'),
    path('items/', CartViewSet.as_view({'post': 'create'}), name='item_create'),
    path('items/<int:pk>/', CartViewSet.as_view({'patch': 'partial_update', 'delete': 'destroy'}),
         name='item_detail'),
]
