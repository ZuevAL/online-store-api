from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView, TopUpView, UserProfileView


app_name = 'users'

urlpatterns = [
    path('users/register/', RegisterView.as_view(), name='register'),
    path('users/me/', UserProfileView.as_view(), name='profile'),
    path('users/me/top-up/', TopUpView.as_view(), name='top_up'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
