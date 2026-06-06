from django.urls import path
from . import views


urlpatterns = [
    path("internal/ingredients/", views.internal_ingredient_physical_data, name="internal_ingredient_physical_data"),
    path("foods/", views.food_list, name="food_list"),
    path("foods/<str:id>/", views.food_detail, name="food_detail"),
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/<str:id>/", views.ingredient_detail, name="ingredient_detail"),
]
