from django.urls import path
from . import views


urlpatterns = [
    path("meals/from-inference/", views.meal_from_inference, name="meal_from_inference"),
    path("meals/barcode/", views.meal_from_barcode, name="meal_from_barcode"),
    path("meals/search/", views.meal_search, name="meal_search"),
    path("meals/manual/", views.meal_manual, name="meal_manual"),
    path("meals/", views.meal_list, name="meal_list"),
    path("meals/<str:id>/", views.meal_detail, name="meal_detail"),
    path("logs/daily/", views.daily_log, name="daily_log"),
    path("logs/range/", views.range_logs, name="range_logs"),
]
