from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from user.views import LoginView, LogoutView, MeView

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token-verify"),
]
