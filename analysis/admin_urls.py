from django.urls import path
from . import views


urlpatterns = [
    path("meals/", views.admin_meal_list, name="admin_meal_list"),
    path("meals/<str:id>/", views.admin_meal_detail, name="admin_meal_detail"),
    path("logs/", views.admin_log_list, name="admin_log_list"),
    path("logs/<str:id>/", views.admin_log_detail, name="admin_log_detail"),
]
