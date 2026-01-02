from celery import shared_task
from django.utils import timezone
from Project.models import Task
from Project.tasks import send_overdue_task_email
from datetime import timedelta

def check_and_send_overdue_emails():
    now = timezone.now()
    for task in Task.objects.all():
        allocated = float(task.allocated_hours)
        consumed = float(task.consumed_hours)
        remaining = allocated - consumed
        # Send 1 hour before and 30 minutes before
        if 0.5 < remaining <= 1:
            send_overdue_task_email.delay(task.id, task.assigned_to_id, 1)
        elif 0 < remaining <= 0.5:
            send_overdue_task_email.delay(task.id, task.assigned_to_id, 0.5)
