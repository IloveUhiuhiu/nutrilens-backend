from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login, name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("otp/request/", views.otp_request, name="otp_request"),
    path("otp/verify/", views.otp_verify, name="otp_verify"),
    path("logout/", views.logout, name="logout"),
]