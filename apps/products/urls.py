from django.urls import path

from .views import ProductViewSet


app_name = 'products'

urlpatterns = [
    path('', ProductViewSet.as_view({'get': 'list', 'post': 'create'}), name='list'),
    path('<int:pk>/', ProductViewSet.as_view({'patch': 'partial_update', 'delete': 'destroy'}), name='detail'),
]
