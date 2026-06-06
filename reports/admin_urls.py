from django.urls import path
from . import views


urlpatterns = [
    path("users/", views.admin_users_dashboard, name="admin_users_dashboard"),
    path("nutrition/", views.admin_nutrition_dashboard, name="admin_nutrition_dashboard"),
    path("inference/", views.admin_inference_dashboard, name="admin_inference_dashboard"),
    path("system-usage/", views.admin_system_usage_dashboard, name="admin_system_usage_dashboard"),
]
