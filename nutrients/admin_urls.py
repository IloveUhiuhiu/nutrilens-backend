from django.urls import path
from . import views


urlpatterns = [
    path("foods/", views.admin_food_list_create, name="admin_food_list_create"),
    path("foods/<str:id>/", views.admin_food_detail, name="admin_food_detail"),
    path("ingredients/", views.admin_ingredient_list_create, name="admin_ingredient_list_create"),
    path("ingredients/<str:id>/", views.admin_ingredient_detail, name="admin_ingredient_detail"),
    path("advice-rules/", views.admin_advice_rule_list_create, name="admin_advice_rule_list_create"),
    path("advice-rules/<int:id>/", views.admin_advice_rule_detail, name="admin_advice_rule_detail"),
    path("packaged-foods/", views.admin_packaged_food_list_create, name="admin_packaged_food_list_create"),
    path("packaged-foods/<str:id>/", views.admin_packaged_food_detail, name="admin_packaged_food_detail"),
]
