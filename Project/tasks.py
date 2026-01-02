from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from Project.models import Task
from accounts.models import Account

@shared_task
def send_overdue_task_email(task_id, user_id, hours_before):
    try:
        task = Task.objects.get(id=task_id)
        user = Account.objects.get(id=user_id)
        subject = f"Task '{task.title}' is about to be overdue"
        message = (
            f"Dear {user.get_full_name() or user.username},\n\n"
            f"Your task '{task.title}' will exceed its allocated hours in {hours_before} hour(s).\n"
            f"Allocated hours: {task.allocated_hours}\n"
            f"Consumed hours: {task.consumed_hours}\n"
            f"Please take necessary action.\n\n"
            f"Regards,\nTeam"
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as e:
        # Optionally log the error
        pass
