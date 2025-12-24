from rest_framework import serializers
from .models import Project, ProjectBudget, Task, Timesheet, TimesheetEntry, TaskTimerLog


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
        if not data.get('use_quoted_amounts'):
            for field in ['total_hours', 'total_budget']:
                if not data.get(field):
                    raise serializers.ValidationError(
                        f"{field.replace('_',' ')} is required"
                    )
        return data
    
# class ProjectCreateSerializer(serializers.ModelSerializer):
#     budget = ProjectBudgetSerializer(required=False)

#     class Meta:
#         model = Project
#         fields = (
#             'status',
#             'project_no',
#             'project_name',
#             'project_type',
#             'start_date',
#             'end_date',
#             'project_manager',
#             'created_from_quotation',
#             'budget',
    
#         )

#     def create(self, validated_data):
#         # Restrict project creation only from confirmed quotations
#         quotation = validated_data.get('created_from_quotation')
#         budget_data = validated_data.get('budget', {})
#         if quotation and hasattr(quotation, 'status'):
#             if quotation.status != 'Confirmed':
#                 raise serializers.ValidationError({
#                     'error': 'Project can only be created from a Confirmed quotation.'
#                 })
#         # If use_quoted_amounts is True, quotation must be present
#         if budget_data and budget_data.get('use_quoted_amounts') and not quotation:
#             raise serializers.ValidationError(
#                 'Quotation is required when using quoted amounts.'
#             )
#         budget_data = validated_data.pop('budget', None)
#         project = Project.objects.create(**validated_data)
#         if budget_data:
#             budget = ProjectBudget.objects.create(
#                 project=project,
#                 **budget_data
#             )
#             if budget.use_quoted_amounts:
#                 budget.apply_quoted_amounts()
#                 budget.save()
#         return project
#     def validate (self, data):
#         start_date = data.get('start_date')
#         end_date = data.get('end_date')
#         if start_date and end_date and end_date < start_date:
#             raise serializers.ValidationError(
#                 "End date cannot be before start date."
#             )
#         return data

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

    def validate(self, data):
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                "End date cannot be before start date."
            )

        quotation = data.get('created_from_quotation')
        if quotation:
            if Project.objects.filter(
                created_from_quotation=quotation
            ).exists():
                raise serializers.ValidationError({
                    "created_from_quotation": "A project already exists for this quotation."
                })

            if hasattr(quotation, 'status') and quotation.status != 'Confirmed':
                raise serializers.ValidationError({
                    "created_from_quotation": "Project can only be created from a Confirmed quotation."
                })

        return data

    def create(self, validated_data):
        budget_data = validated_data.pop('budget', None)
        project = Project.objects.create(**validated_data)

        if budget_data:
            budget = ProjectBudget.objects.create(
                project=project,
                **budget_data
            )
            if budget.use_quoted_amounts:
                budget.apply_quoted_amounts()
                budget.save()

        return project
    
class TaskSerializer(serializers.ModelSerializer):

    created_by = serializers.SerializerMethodField()
    modified_by = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()
    consumed_hours = serializers.SerializerMethodField()
    remaining_hours = serializers.SerializerMethodField()


    def get_project(self, obj):
        return {
            'project_name': obj.project.project_name
        } if obj.project else None

    def get_created_by(self, obj):
        return obj.created_by.username if obj.created_by else None

    def get_modified_by(self, obj):
        return obj.modified_by.username if obj.modified_by else None
    
    def get_consumed_hours(self, obj):
        return obj.consumed_hours

    def get_remaining_hours(self, obj):
        return obj.remaining_hours

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "allocated_hours",
            "consumed_hours",
            "remaining_hours",
            "allocated_hours",
            "assigned_to",
            "project",
            "created_by",
            "modified_by",
            "status",
        ]

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
    entries = TimesheetEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Timesheet
        fields = [
            'id', 'week_start', 'week_end',
            'status', 'entries'
        ]



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