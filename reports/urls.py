from django.urls import path
from . import views


urlpatterns = [
    path("nutrition/summary/", views.nutrition_summary, name="nutrition_summary"),
    path("nutrition/trends/", views.nutrition_trends, name="nutrition_trends"),
    path("nutrition/advice/", views.nutrition_advice, name="nutrition_advice"),
]
