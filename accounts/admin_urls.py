from django.urls import path
from . import views

urlpatterns = [
    path("quota/", views.admin_quota_update, name="admin_quota_update"),
    path("", views.admin_account_list, name="admin_account_list"),
    path("<str:id>/", views.admin_account_detail, name="admin_account_detail"),
    path("<str:id>/status/", views.admin_account_status, name="admin_account_status"),
    path("<str:id>/reset/", views.admin_account_reset_password, name="admin_account_reset_password"),
    path("<str:id>/role/", views.admin_account_role, name="admin_account_role"),
]
