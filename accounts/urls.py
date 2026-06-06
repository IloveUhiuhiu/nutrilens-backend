from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("register/", views.register, name="register"),
    path("activity-levels/", views.activity_level_list, name="activity_level_list"),
    path("login/", views.login, name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("otp/request/", views.otp_request, name="otp_request"),
    path("otp/verify/", views.otp_verify, name="otp_verify"),
    path("password/forgot/", views.password_forgot, name="password_forgot"),
    path("password/reset/", views.password_reset, name="password_reset"),
    path("password/change/", views.password_change, name="password_change"),
    path("profile/", views.profile, name="profile"),
    path("logout/", views.logout, name="logout"),
]
