from django.urls import path
from . import views


urlpatterns = [
    path("jobs/", views.admin_job_list, name="admin_inference_job_list"),
    path("jobs/<str:id>/", views.admin_job_detail, name="admin_inference_job_detail"),
    path("metrics/", views.admin_metrics, name="admin_inference_metrics"),
    path("feedback/", views.admin_feedback_list, name="admin_inference_feedback_list"),
    path("feedback/<str:id>/", views.admin_feedback_review, name="admin_inference_feedback_review"),
]
