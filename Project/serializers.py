from rest_framework import serializers
from .models import (Project, ProjectBudget, Task, Timesheet, TimesheetEntry, TaskTimerLog,
                      TaskExtraHoursRequest)
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import Account
from client.serializers import PointOfContactSerializer

class ProjectBudgetSerializer(serializers.ModelSerializer):
    forecasted_profit = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = ProjectBudget
        fields = (
            'use_quoted_amounts',
            'total_hours',
            'total_budget',
            'bills_and_expenses',
            'currency',
            'forecasted_profit',
        )

    def validate(self, data):
        project_type = self.context.get('project_type')

        # Quoted amounts → model will fill values
        if data.get('use_quoted_amounts'):
            return data

        # Manual budget
        if project_type == 'external':
            # STRICT for external
            missing = []
            if not data.get('total_hours'):
                missing.append("total hours")
            if not data.get('total_budget'):
                missing.append("total budget")

            if missing:
                raise serializers.ValidationError(
                    f"{', '.join(missing)} is required"
                )

        # Internal → manual budget is OPTIONAL
        return data

    
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError


class ProjectCreateSerializer(serializers.ModelSerializer):
    budget = ProjectBudgetSerializer(required=False)

    class Meta:
        model = Project
        fields = (
            'status',
            'project_no',
            'project_name',
            'project_type',
            'start_date',
            'end_date',
            'project_manager',
            'created_from_quotation',
            'budget',
        )
    def get_fields(self):
        fields = super().get_fields()

        # Safely determine project_type
        project_type = None

        if hasattr(self, 'initial_data'):
            project_type = self.initial_data.get('project_type')
        elif self.instance:
            project_type = getattr(self.instance, 'project_type', None)

        fields['budget'] = ProjectBudgetSerializer(
            required=False,
            context={'project_type': project_type}
        )
        return fields


    def validate(self, data):
        project_type = data.get('project_type')
        quotation = data.get('created_from_quotation')
        budget = data.get('budget')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # 🔒 Common date validation
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                "End date cannot be before start date."
            )

        # =============================
        # 🔹 INTERNAL PROJECT
        # =============================
        if project_type == 'internal':

            # Quotation should not be used
            if quotation:
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        "Quotation is not applicable for internal projects."
                    )
                })

            # Budget is OPTIONAL, but must be MANUAL if provided
            if budget and budget.get('use_quoted_amounts'):
                raise serializers.ValidationError({
                    "budget": {
                        "use_quoted_amounts": (
                            "Internal projects cannot use quoted amounts."
                        )
                    }
                })

            return data

        # =============================
        # 🔹 EXTERNAL PROJECT
        # =============================
        if project_type == 'external':

            # 1️⃣ Quotation is mandatory
            if not quotation:
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        "Quotation is required for external projects."
                    )
                })

            # 2️⃣ Budget is mandatory
            if not budget:
                raise serializers.ValidationError({
                    "budget": "Budget is required for external projects."
                })

            # 3️⃣ Quotation status validation
            invalid_statuses = ['Rejected', 'Cancelled', 'Closed']
            if quotation.status in invalid_statuses:
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        f"Project cannot be created because the quotation is {quotation.status}."
                    )
                })

            if quotation.status != 'Confirmed':
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        "Project can only be created from a Confirmed quotation."
                    )
                })

            # 4️⃣ Prevent duplicate project creation
            if Project.objects.filter(created_from_quotation=quotation).exists():
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        "A project already exists for this quotation."
                    )
                })

        return data

    def create(self, validated_data):
        budget_data = validated_data.pop('budget', None)

        project = Project.objects.create(**validated_data)

        # 🔹 Create budget only if provided
        if budget_data:
            budget = ProjectBudget.objects.create(
                project=project,
                **budget_data
            )

            # Apply quoted amounts if selected
            if budget.use_quoted_amounts:
                try:
                    budget.apply_quoted_amounts()
                    budget.save()
                except DjangoValidationError as e:
                    raise serializers.ValidationError({"budget": e.messages})

        return project



from finances.serializers import InvoiceListSerializer
class ProjectListSerializer(serializers.ModelSerializer):
    budget = serializers.SerializerMethodField()
    invoices = serializers.SerializerMethodField()
    company_name = serializers.CharField(
        source='client.company_name',
        read_only=True
    )
    contacts=serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            'project_no',
            'project_name',
            'status',
            'start_date',
            'end_date',
            'budget',
            'invoices',
            'company_name',
            'contacts',
            'created_from_quotation',
        )

    def get_budget(self, obj):
        try:
            return ProjectBudgetSerializer(obj.budget).data
        except ObjectDoesNotExist:
            return None
    def get_invoices(self, obj):
        invoices = obj.invoice_set.all()  # ✅ CORRECT

        if not invoices.exists():
            return []

        return InvoiceListSerializer(invoices, many=True).data
    def get_contacts(self, obj):
        """Get all POCs (contacts) for the project's client company"""
        if not obj.client:
            return []
        
        pocs = obj.client.pocs.all()
        return PointOfContactSerializer(pocs, many=True).data
    

class TaskSerializer(serializers.ModelSerializer):
    # due_date = serializers.DateField(required=True)
    created_by = serializers.SerializerMethodField(read_only=True)
    modified_by = serializers.SerializerMethodField(read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        required=False,
        allow_null=True
    )
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=True
    )
    project_name = serializers.SerializerMethodField(read_only=True)
    consumed_hours = serializers.SerializerMethodField(read_only=True)
    remaining_hours = serializers.SerializerMethodField(read_only=True)
    allocated_formatted = serializers.SerializerMethodField(read_only=True)
    consumed_formatted = serializers.SerializerMethodField(read_only=True)
    remaining_formatted_hms = serializers.SerializerMethodField(read_only=True)
    needs_extra_hours = serializers.SerializerMethodField(read_only=True)
    total_seconds = serializers.SerializerMethodField(read_only=True)
    running = serializers.SerializerMethodField(read_only=True)
    started_at = serializers.SerializerMethodField(read_only=True)
    is_stopped = serializers.SerializerMethodField(read_only=True)
    stop_reason = serializers.SerializerMethodField(read_only=True)
    stopped_at = serializers.SerializerMethodField(read_only=True)
    remaining_seconds = serializers.SerializerMethodField(read_only=True)
    remaining_formatted = serializers.SerializerMethodField(read_only=True)
    exceeded_by_seconds = serializers.SerializerMethodField(read_only=True)
    exceeded_formatted = serializers.SerializerMethodField(read_only=True)
    has_extra_hours_request = serializers.SerializerMethodField(read_only=True)
    # has_pending_extra_hours_request = serializers.SerializerMethodField(read_only=True)
    # has_approved_extra_hours_request = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "allocated_hours",
            "allocated_formatted",
            "consumed_hours",
            "remaining_hours",
            "consumed_formatted",
            "remaining_formatted_hms",
            "assigned_to",
            "project",
            "project_name",
            "created_by",
            "modified_by",
            "due_date",
            "needs_extra_hours",
            "total_seconds",
            "running",
            "started_at",
            "is_stopped",
            "stop_reason",
            "stopped_at",
            "remaining_seconds",
            "remaining_formatted",
            "exceeded_by_seconds",
            "exceeded_formatted",
            "has_extra_hours_request",
           
            # "is_extra_hours_requested"
        ]
        read_only_fields = [
            "created_by",
            "modified_by",
            "consumed_hours",
            "remaining_hours",
            "allocated_formatted",
            "has_extra_hours_request",
            "needs_extra_hours",
            "total_seconds",
            "running",
            "started_at",
            "is_stopped",
            "stop_reason",
            "stopped_at",
            "remaining_seconds",
            "remaining_formatted",
            "exceeded_by_seconds",
            "exceeded_formatted",
        ]

    def get_project_name(self, obj):
        return obj.project.project_name if obj.project else None


    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_modified_by(self, obj):
        return obj.modified_by.username if obj.modified_by else None

    def get_consumed_hours(self, obj):
        return obj.consumed_hours

    def get_remaining_hours(self, obj):
        return obj.remaining_hours

    def get_allocated_formatted(self, obj):
        try:
            from Project.utils import format_seconds
            seconds = int(float(obj.allocated_hours) * 3600)
            return format_seconds(seconds)["formatted"]
        except Exception:
            return None

    def get_consumed_formatted(self, obj):
        try:
            from Project.utils import format_seconds
            seconds = int(float(obj.consumed_hours) * 3600)
            return format_seconds(seconds)["formatted"]
        except Exception:
            return None

    def get_remaining_formatted_hms(self, obj):
        try:
            from Project.utils import format_seconds
            seconds = int(float(obj.remaining_hours) * 3600)
            return format_seconds(seconds)["formatted"]
        except Exception:
            return None

    def get_has_extra_hours_request(self, obj):
        """Backward-compatible: true only if a pending request exists"""
        from .models import TaskExtraHoursRequest
        return TaskExtraHoursRequest.objects.filter(
            task=obj,
            status='pending'
        ).exists()

    def get_has_pending_extra_hours_request(self, obj):
        from .models import TaskExtraHoursRequest
        return TaskExtraHoursRequest.objects.filter(task=obj, status='pending').exists()

    def get_has_approved_extra_hours_request(self, obj):
        from .models import TaskExtraHoursRequest
        return TaskExtraHoursRequest.objects.filter(task=obj, status='approved').exists()

    def get_needs_extra_hours(self, obj):
        try:
            allocated = float(obj.allocated_hours)
            consumed = float(obj.consumed_hours)
            return consumed > allocated
        except Exception:
            return False

    def get_total_seconds(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return None
        from Project.redis_utils import get_active_timer
        from Project.models import TaskTimerLog
        user = request.user
        # Sum all previous logs for this user and task
        previous_logs = TaskTimerLog.objects.filter(task=obj, user=user, is_active=False)
        prev_seconds = sum([(log.end_time - log.start_time).total_seconds() for log in previous_logs if log.end_time and log.start_time])
        prev_seconds = int(prev_seconds)
        # If running, add current session
        redis_task, redis_start = get_active_timer(user.id)
        if redis_task and int(redis_task) == obj.id and redis_start:
            from django.utils import timezone
            start_time = timezone.datetime.fromisoformat(redis_start.decode())
            elapsed_seconds = int((timezone.now() - start_time).total_seconds())
            return prev_seconds + elapsed_seconds
        return prev_seconds

    def get_running(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return False
        from Project.redis_utils import get_active_timer
        redis_task, _ = get_active_timer(request.user.id)
        return bool(redis_task and int(redis_task) == obj.id)

    def get_started_at(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return None
        from Project.redis_utils import get_active_timer
        redis_task, redis_start = get_active_timer(request.user.id)
        if redis_task and int(redis_task) == obj.id and redis_start:
            return redis_start.decode()
        return None

    def get_is_stopped(self, obj):
        """Check if task has been stopped today (has timesheet entry for today)"""
        request = self.context.get('request')
        if not request or not hasattr(request, 'user'):
            return False
        from django.utils import timezone
        from Project.models import TimesheetEntry
        today = timezone.now().date()
        return TimesheetEntry.objects.filter(
            timesheet__user=request.user,
            task=obj,
            date=today
        ).exists()

    def _get_time_stats(self, obj):
        """Compute stop metadata for serializer consumers"""
        # Always use the task's assigned user, not the current request user
        # This ensures PMs see the assigned employee's stats, not the PM's own (empty) stats
        user = obj.assigned_to
        
        if not user:
            return None

        from Project.models import TaskTimerLog
        from Project.utils import format_seconds

        logs = TaskTimerLog.objects.filter(
            task=obj,
            user=user,
            is_active=False,
            end_time__isnull=False,
            start_time__isnull=False
        )

        if not logs.exists():
            return {
                "total_seconds": 0,
                "stopped_at": None,
                "stop_reason": None,
                "remaining_seconds": int(float(obj.allocated_hours) * 3600),
                "remaining_formatted": format_seconds(float(obj.allocated_hours) * 3600)["formatted"],
                "exceeded_by_seconds": 0,
                "exceeded_formatted": "00:00:00",
            }

        total_seconds = int(sum((log.end_time - log.start_time).total_seconds() for log in logs))
        last_log = logs.order_by("-end_time").first()
        allocated_seconds = int(float(obj.allocated_hours) * 3600)
        remaining_seconds = max(allocated_seconds - total_seconds, 0)
        exceeded_by_seconds = max(total_seconds - allocated_seconds, 0)

        stop_reason = None
        if not self.get_running(obj):
            stop_reason = "AUTO" if exceeded_by_seconds > 0 else "COMPLETED"

        return {
            "total_seconds": total_seconds,
            "stopped_at": last_log.end_time.isoformat() if last_log and last_log.end_time else None,
            "stop_reason": stop_reason,
            "remaining_seconds": remaining_seconds,
            "remaining_formatted": format_seconds(remaining_seconds)["formatted"],
            "exceeded_by_seconds": exceeded_by_seconds,
            "exceeded_formatted": format_seconds(exceeded_by_seconds)["formatted"],
        }

    def get_stop_reason(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("stop_reason") if stats else None

    def get_stopped_at(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("stopped_at") if stats else None

    def get_remaining_seconds(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("remaining_seconds") if stats else None

    def get_remaining_formatted(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("remaining_formatted") if stats else None

    def get_exceeded_by_seconds(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("exceeded_by_seconds") if stats else None

    def get_exceeded_formatted(self, obj):
        stats = self._get_time_stats(obj)
        return stats.get("exceeded_formatted") if stats else None

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Replace assigned_to with user object if present
        if instance.assigned_to:
            rep["assigned_to"] = {
                "id": instance.assigned_to.id,
                "username": instance.assigned_to.username
            }
        else:
            rep["assigned_to"] = None
        return rep
class TimesheetEntrySerializer(serializers.ModelSerializer):

    def validate(self, attrs):
        entry_date = attrs['date']

        # ❌ Sunday restricted
        if entry_date.weekday() == 6:
            raise serializers.ValidationError(
                "Sunday time entry is not allowed."
            )

        # ✅ Monday–Friday normal
        # ✅ Saturday optional
        return attrs

    class Meta:
        model = TimesheetEntry
        fields = ['id', 'task', 'date', 'hours']


class TimesheetSerializer(serializers.ModelSerializer):
    entries = TimesheetEntrySerializer(many=True)

    class Meta:
        model = Timesheet
        fields = [
            'id',
            'user',
            'week_start',
            'week_end',
            'status',
            'entries'
        ]
        read_only_fields = ['user', 'status']

    def create(self, validated_data):
        entries_data = validated_data.pop('entries')
        timesheet = Timesheet.objects.create(**validated_data)

        for entry in entries_data:
            TimesheetEntry.objects.create(
                timesheet=timesheet,
                **entry
            )

        return timesheet

class TimesheetEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimesheetEntry
        fields = ['id', 'task', 'date', 'hours']


class TimesheetSerializer(serializers.ModelSerializer):
    entries = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Timesheet
        fields = [
            'id', 'week_start', 'week_end',
            'status', 'entries'
        ]

    def get_entries(self, obj):
        """Populate entries with a unified logic that matches weekly summary.

        If `week_start` and `week_end` are provided in context, return entries
        for the object's user within that date range (task not null). Otherwise,
        fall back to entries attached to this timesheet.
        """
        from .models import TimesheetEntry

        week_start = self.context.get('week_start')
        week_end = self.context.get('week_end')
        include_orphans = bool(self.context.get('include_orphans'))

        if week_start and week_end:
            qs = TimesheetEntry.objects.filter(
                timesheet__user=obj.user,
                date__gte=week_start,
                date__lte=week_end,
            ).select_related('task')
        else:
            qs = TimesheetEntry.objects.filter(
                timesheet=obj,
            ).select_related('task')
        if not include_orphans:
            qs = qs.filter(task__isnull=False)

        # Local import to avoid circulars
        from .utils import format_seconds

        out = []
        for e in qs:
            out.append({
                'id': e.id,
                'task': e.task.id if e.task else None,
                'date': e.date,
                'hours': float(e.hours),
                'hours_formatted': format_seconds(int(round(float(e.hours) * 3600)))['formatted'],
            })
        return out



class TaskTimerLogSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = TaskTimerLog
        fields = [
            "id",
            "task",
            "task_title",
            "start_time",
            "end_time",
            "duration_minutes",
            "is_active",
            "created_at",
        ]
        read_only_fields = fields



# from rest_framework import serializers

class TaskExtraHoursRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskExtraHoursRequest
        fields = [
            "id",
            # "task",
            "requested_hours",
            "reason",
            "status",
            "created_at"

        ]
        read_only_fields = ["status", "created_at", "previous_allocated_hours", "approved_allocated_hours"]

class TaskExtraHoursReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])


class TimesheetWeeklySummarySerializer(serializers.Serializer):
    """Serializer for weekly timesheet summary"""
    week = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    data = serializers.SerializerMethodField()

    def get_week(self, obj):
        """Extract week info from obj dict"""
        return obj.get('week')

    def get_summary(self, obj):
        """Extract summary from obj dict"""
        return obj.get('summary')

    def get_data(self, obj):
        """Extract data from obj dict"""
        return obj.get('data', [])