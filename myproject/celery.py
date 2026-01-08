import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

app = Celery('myproject')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    'check-running-timers-every-minute': {
        'task': 'Project.tasks.check_running_timers',
        'schedule': 60.0,  # Run every 60 seconds
    },
}