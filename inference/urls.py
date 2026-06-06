from django.urls import path
from . import views


urlpatterns = [
    path("image/", views.image_inference, name="image_inference"),
    path("jobs/<str:id>/", views.job_detail, name="job_detail"),
    path("jobs/<str:id>/result/", views.job_result, name="job_result"),
    path("jobs/<str:id>/feedback/", views.job_feedback, name="job_feedback"),
]
