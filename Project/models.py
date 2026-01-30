
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone


class Project(models.Model):

    STATUS_CHOICES = [
        ("planning", "Planning"),
        ("development", "Development In Progress"),
        ("testing", "Testing In Progress"),
        ("uat", "UAT In Progress"),
        ("ready_for_deployment", "Ready for Deployment"),
        ("deployed", "Deployed"),
        ("on_hold", "On Hold"),
    ]
    PROJECT_TYPE_CHOICES = [
        ('internal', 'Internal'),
        ('external', 'External'),
    ]
    CURRENCY_CHOICES = [
        ('INR', 'INR'),
        ('USD', 'USD'),
        ('EUR', 'EUR'),
    ]
    
    status = models.CharField(
    max_length=50,
    choices=STATUS_CHOICES,
    default="planning"
)
    project_no = models.AutoField(primary_key=True)
    project_name = models.CharField(max_length=255, unique=True)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
    client = models.ForeignKey('client.Company', on_delete=models.SET_NULL, null=True, blank=True)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='INR')
    start_date = models.DateField()
    end_date = models.DateField()
    project_manager = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True)
    created_from_quotation = models.OneToOneField(
        'product_group.Quote',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='project'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.project_type == 'external' and not self.created_from_quotation:
            raise ValidationError("Quotation is required for external projects.")

    def save(self, *args, **kwargs):
        # ✅ AUTO-ASSIGN CLIENT FROM QUOTATION
        if self.created_from_quotation and not self.client:
            self.client = self.created_from_quotation.client

        if self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.project_name} ({self.project_no})"
    
class ProjectBudget(models.Model):
    project = models.OneToOneField(Project, on_delete=models.SET_NULL, null=True, related_name='budget')
    use_quoted_amounts = models.BooleanField(default=True)
    total_hours = models.PositiveIntegerField(null=True, blank=True)
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bills_and_expenses = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='INR')

    def apply_quoted_amounts(self):
        quote = self.project.created_from_quotation
        if not quote:
            raise ValidationError("Quotation is required")

        self.total_hours = sum(
            item.quantity for item in quote.items.all()
            if item.unit == 'hours'
        )
        self.total_budget = quote.total_amount
        self.bills_and_expenses = quote.in_house_cost + quote.outsourced_cost
        self.currency = getattr(quote, 'currency', None) or self.project.currency
        # self.currency = getattr(quote, 'currency', None) or self.project.currency

    @property
    def forecasted_profit(self):
            """
            Expected profit based on current budget and expenses
            """
            if self.total_budget is None or self.bills_and_expenses is None:
                return None
            return self.total_budget - self.bills_and_expenses




class Task(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('needs_attention', 'Needs Attention'),
    ]

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='tasks')
    title = models.CharField(max_length=255)
    assigned_to = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_tasks'
    )
    allocated_hours = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_tasks')
    modified_by = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='modified_tasks'
    )

    def __str__(self):
        return self.title

    @property
    def consumed_hours(self):
        """Calculate consumed hours from TaskTimerLog (real-time tracking)"""
        from django.db.models import Sum, Q
        from decimal import Decimal
        
        # Get all completed timer logs for this task
        timer_logs = TaskTimerLog.objects.filter(
            task=self,
            is_active=False,
            end_time__isnull=False,
            start_time__isnull=False
        )
        
        total_seconds = 0
        for log in timer_logs:
            duration = (log.end_time - log.start_time).total_seconds()
            total_seconds += duration
        
        # Convert seconds to hours
        hours = Decimal(total_seconds) / Decimal(3600)
        return hours

    @property
    def remaining_hours(self):
        return max(self.allocated_hours - self.consumed_hours, 0)


class Timesheet(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    week_start = models.DateField()  # Sunday
    week_end = models.DateField()    # Saturday
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'week_start')

    def __str__(self):
        return f"{self.user} | {self.week_start}"



class TimesheetEntry(models.Model):
    timesheet = models.ForeignKey(
        Timesheet,
        on_delete=models.SET_NULL,
        null=True,
        related_name='entries'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        related_name='time_entries'
    )
    date = models.DateField()
    hours = models.DecimalField(max_digits=6, decimal_places=4)

    class Meta:
        unique_together = ('timesheet', 'task', 'date')


class TaskTimerLog(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="timer_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)

    duration_minutes = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_extra = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.task} - {self.duration_minutes} mins"
    
    @staticmethod
    def get_total_seconds(task, user):
        logs = TaskTimerLog.objects.filter(task=task, user=user)
        total = 0
        for log in logs:
            if log.end_time:
                total += (log.end_time - log.start_time).total_seconds()
            else:
                total += (timezone.now() - log.start_time).total_seconds()
        return int(total)


class TaskExtraHoursRequest(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="extra_hour_requests"
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="extra_hour_requests"
    )

    requested_hours = models.DecimalField(max_digits=7, decimal_places=2)
    reason = models.TextField()
    previous_allocated_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    approved_allocated_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_extra_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.task.title} | +{self.requested_hours} hrs"
