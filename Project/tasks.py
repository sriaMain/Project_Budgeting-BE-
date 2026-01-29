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
        company_name = getattr(settings, "COMPANY_NAME", "Project Management Office")
        assignee_name = user.get_full_name() or user.username
        subject = f"Reminder: '{task.title}' is nearing its allocated hours"
        message = (
            f"Dear {assignee_name},\n\n"
            f"This is a reminder that your task '{task.title}' is nearing its allocated effort.\n"
            f"Approx. time left: {hours_before} hour(s)\n"
            f"Allocated hours: {task.allocated_hours}\n"
            f"Consumed hours: {task.consumed_hours}\n\n"
            f"Please ensure timely completion or flag any blockers to your project manager.\n\n"
            f"Regards,\n"
            f"Project Management Office\n"
        
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except Exception as e:
        # Optionally log the error
        pass


@shared_task
def send_task_assignment_email(task_id, user_id):
    """Notify a user when a task is assigned to them."""
    try:
        task = Task.objects.select_related('project').get(id=task_id)
        user = Account.objects.get(id=user_id)

        if not user.email:
            return

        project_name = task.project.project_name if task.project else "Unassigned project"
        # company_name = getattr(settings, "COMPANY_NAME", "Project Management Office")
        assignee_name = user.get_full_name() or user.username
        task_name = task.title
        allocated_hours = task.allocated_hours
        due_date = task.due_date or "Not set"

        subject = f"Task Assigned: {task_name}"
        message = (
            f"Dear {assignee_name},\n\n"
            f"This is to inform you that a task has been assigned to you as part of the {project_name} project.\n\n"
            f"Task Title: {task_name}\n"  
            f"Allocated Effort: {allocated_hours} hours\n"
            f"Due Date: {due_date}\n\n"
            f"Please acknowledge the task and ensure timely completion as per the project plan.\n"
            f"For any dependencies or concerns, notify the project manager at the earliest.\n\n"
            f"Regards,\n"
            f"Project Management Team\n"
            # f"{company_name}"
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception:
        # Avoid raising to keep main flow safe
        pass


@shared_task
def check_running_timers():
    """Check all running timers and auto-stop if allocated hours exceeded"""
    from Project.models import TaskTimerLog
    from Project.redis_utils import get_active_timer, clear_active_timer
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from decimal import Decimal
    
    # Get all active timers
    active_timers = TaskTimerLog.objects.filter(is_active=True).select_related('task', 'user')
    
    for timer in active_timers:
        task = timer.task
        user = timer.user
        
        # Calculate total consumed time including current session
        previous_logs = TaskTimerLog.objects.filter(
            task=task,
            user=user,
            is_active=False,
            end_time__isnull=False,
            start_time__isnull=False
        )
        
        prev_seconds = sum(
            (log.end_time - log.start_time).total_seconds()
            for log in previous_logs
        )
        
        # Add current session time
        current_seconds = (timezone.now() - timer.start_time).total_seconds()
        total_seconds = int(prev_seconds + current_seconds)
        
        # Check if exceeded
        allocated_hours = float(task.allocated_hours)
        allocated_seconds = int(allocated_hours * 3600)
        
        if total_seconds >= allocated_seconds:
            # Auto-stop the timer
            timer.end_time = timezone.now()
            timer.is_active = False
            timer.duration_minutes = int((timer.end_time - timer.start_time).total_seconds()) // 60
            timer.save()
            
            # Clear Redis
            clear_active_timer(user.id)
            
            # Calculate final values
            final_logs = TaskTimerLog.objects.filter(
                task=task,
                user=user,
                is_active=False,
                end_time__isnull=False,
                start_time__isnull=False
            )
            final_seconds = int(sum(
                (log.end_time - log.start_time).total_seconds()
                for log in final_logs
            ))
            
            exceeded_by_seconds = max(0, final_seconds - allocated_seconds)
            
            # ✅ UPDATE TIMESHEET with allowed hours only
            from Project.models import Timesheet, TimesheetEntry
            from Project.utils import get_week_range
            
            entry_date = timezone.now().date()
            week_start, week_end = get_week_range(entry_date)
            
            timesheet, _ = Timesheet.objects.get_or_create(
                user=user,
                week_start=week_start,
                defaults={"week_end": week_end}
            )
            
            # Only log up to allocated hours
            hours_to_add = Decimal(str(min(allocated_seconds, final_seconds))) / Decimal("3600")
            
            entry, created = TimesheetEntry.objects.get_or_create(
                timesheet=timesheet,
                task=task,
                date=entry_date,
                defaults={"hours": hours_to_add}
            )
            
            if not created:
                entry.hours = hours_to_add
                entry.save()
            
            # Send WebSocket event
            from Project.utils import format_seconds
            formatted_total = format_seconds(final_seconds)
            formatted_exceeded = format_seconds(exceeded_by_seconds)
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "timer_event",
                    "data": {
                        "event": "TASK_AUTO_STOPPED",
                        "task_id": task.id,
                        "task_title": task.title,
                        "allocated_hours": allocated_hours,
                        "total_seconds": final_seconds,
                        "exceeded_by_seconds": exceeded_by_seconds,
                        "stop_reason": "AUTO",
                        "stopped_at": timezone.now().isoformat(),
                        "formatted_time": formatted_total,
                        "formatted_exceeded": formatted_exceeded,
                        "running": False,
                        "timesheet_updated": True,
                        "hours_logged": float(hours_to_add),
                        "message": "Task automatically stopped because allocated time was exceeded."
                    }
                }
            )