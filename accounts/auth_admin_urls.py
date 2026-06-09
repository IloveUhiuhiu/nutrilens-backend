from django.urls import path
from . import auth_admin_views as views

urlpatterns = [
    path("groups/", views.admin_group_list_create, name="admin_group_list_create"),
    path("groups/<int:id>/", views.admin_group_detail, name="admin_group_detail"),
    path("permissions/", views.admin_permission_list, name="admin_permission_list"),
]
