import os
from celery import Celery

# Thiết lập môi trường Django mặc định cho 'celery'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")

app.config_from_object('django.conf:settings', namespace='CELERY')

# Tự động tìm các tasks.py trong các app đã đăng ký
app.autodiscover_tasks()