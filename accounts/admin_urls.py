from django.urls import path
from . import views
from .auth_admin_views import admin_user_permissions

urlpatterns = [
    path("quota/", views.admin_quota, name="admin_quota"),
    path("otp/", views.admin_otp_list, name="admin_otp_list"),
    path("activity-levels/", views.admin_activity_level_list_create, name="admin_activity_level_list_create"),
    path("activity-levels/<int:id>/", views.admin_activity_level_detail, name="admin_activity_level_detail"),
    path("", views.admin_account_list, name="admin_account_list"),
    path("<str:id>/permissions/", admin_user_permissions, name="admin_user_permissions"),
    path("<str:id>/status/", views.admin_account_status, name="admin_account_status"),
    path("<str:id>/reset/", views.admin_account_reset_password, name="admin_account_reset_password"),
    path("<str:id>/role/", views.admin_account_role, name="admin_account_role"),
    path("<str:id>/", views.admin_account_detail, name="admin_account_detail"),
]
