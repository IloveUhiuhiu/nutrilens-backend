import uuid
from django.conf import settings
from django.db import models


class InferenceJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inference_jobs')
    image = models.ImageField(upload_to='inference/images/', blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True)
    depth_map = models.FileField(upload_to='inference/depth_maps/', blank=True)
    camera_metadata = models.JSONField(default=dict, blank=True)
    depth_metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    model_version = models.CharField(max_length=100, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    raw_output = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Chức năng: lưu inference job và sinh id. Đầu vào: args/kwargs save. Đầu ra: InferenceJob được lưu."""
        if not self.id:
            self.id = f"inf_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn inference job. Đầu vào: instance. Đầu ra: id và trạng thái."""
        return f"{self.id} - {self.status}"


class InferenceResult(models.Model):
    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    job = models.OneToOneField(InferenceJob, on_delete=models.CASCADE, related_name='result')
    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    total_weight = models.FloatField(default=0)
    components = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Chức năng: lưu inference result và sinh id. Đầu vào: args/kwargs save. Đầu ra: InferenceResult được lưu."""
        if not self.id:
            self.id = f"res_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn inference result. Đầu vào: instance. Đầu ra: job id."""
        return f"Result {self.job_id}"


class InferenceFeedback(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
    ]

    id = models.CharField(primary_key=True, max_length=20, editable=False, unique=True)
    job = models.ForeignKey(InferenceJob, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inference_feedbacks')
    issue_type = models.CharField(max_length=100)
    comment = models.TextField(blank=True)
    corrected_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        """Chức năng: lưu feedback và sinh id. Đầu vào: args/kwargs save. Đầu ra: InferenceFeedback được lưu."""
        if not self.id:
            self.id = f"fb_{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        """Chức năng: biểu diễn feedback. Đầu vào: instance. Đầu ra: id và issue_type."""
        return f"Feedback {self.id} - {self.issue_type}"
