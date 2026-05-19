from django.contrib import admin
from .models import InferenceFeedback, InferenceJob, InferenceResult


@admin.register(InferenceJob)
class InferenceJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'model_version', 'latency_ms', 'created_at')
    list_filter = ('status', 'model_version')
    search_fields = ('id', 'user__email')


@admin.register(InferenceResult)
class InferenceResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'total_calories', 'total_weight', 'created_at')
    search_fields = ('id', 'job__id')


@admin.register(InferenceFeedback)
class InferenceFeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'job', 'user', 'issue_type', 'status', 'created_at')
    list_filter = ('status', 'issue_type')
    search_fields = ('id', 'job__id', 'user__email')
