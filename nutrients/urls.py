from django.urls import path
from . import views


urlpatterns = [
    path("foods/", views.food_list, name="food_list"),
    path("foods/<str:id>/", views.food_detail, name="food_detail"),
    path("ingredients/", views.ingredient_list, name="ingredient_list"),
    path("ingredients/<str:id>/", views.ingredient_detail, name="ingredient_detail"),
    path("barcodes/<str:barcode>/", views.packaged_food_by_barcode, name="packaged_food_by_barcode"),
]
