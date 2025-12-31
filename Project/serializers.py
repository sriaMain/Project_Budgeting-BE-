from rest_framework import serializers
from .models import Project, ProjectBudget, Task, Timesheet, TimesheetEntry, TaskTimerLog, TaskExtraHoursRequest
from django.core.exceptions import ObjectDoesNotExist
from accounts.models import Account

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

#     def validate(self, data):
#         start_date = data.get('start_date')
#         end_date = data.get('end_date')

#         if start_date and end_date and end_date < start_date:
#             raise serializers.ValidationError(
#                 "End date cannot be before start date."
#             )

#         quotation = data.get('created_from_quotation')
#         if quotation:
#             if Project.objects.filter(
#                 created_from_quotation=quotation
#             ).exists():
#                 raise serializers.ValidationError({
#                     "created_from_quotation": "A project already exists for this quotation."
#                 })

#             if hasattr(quotation, 'status') and quotation.status != 'Confirmed':
#                 raise serializers.ValidationError({
#                     "created_from_quotation": "Project can only be created from a Confirmed quotation."
#                 })

#         return data

#     def create(self, validated_data):
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
        project_type = data.get('project_type')
        quotation = data.get('created_from_quotation')

    
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError(
                "End date cannot be before start date."
            )

        
        if project_type == 'internal':
            # Quotation is NOT required
            return data

        if project_type == 'external':

            if not quotation:
                raise serializers.ValidationError({
                    "created_from_quotation": "Quotation is required for external projects."
                })

        
            invalid_statuses = ['Rejected', 'Cancelled', 'Closed']
            if quotation.status in invalid_statuses:
                raise serializers.ValidationError({
                    "created_from_quotation": (
                        f"Project cannot be created because the quotation is {quotation.status}."
                    )
                })

           
            if quotation.status != 'Confirmed':
                raise serializers.ValidationError({
                    "created_from_quotation": "Project can only be created from a Confirmed quotation."
                })

            if Project.objects.filter(created_from_quotation=quotation).exists():
                raise serializers.ValidationError({
                    "created_from_quotation": "A project already exists for this quotation."
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


class ProjectListSerializer(serializers.ModelSerializer):
    budget = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = (
            'project_no',
            'project_name',
            'status',
            'start_date',
            'end_date',
            'budget',
        )

    def get_budget(self, obj):
        try:
            return ProjectBudgetSerializer(obj.budget).data
        except ObjectDoesNotExist:
            return None
    
# class TaskSerializer(serializers.ModelSerializer):

#     created_by = serializers.SerializerMethodField()
#     modified_by = serializers.SerializerMethodField()
#     project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=True)
#     consumed_hours = serializers.SerializerMethodField()
#     remaining_hours = serializers.SerializerMethodField()



#     # Optionally, if you want to keep the project_name in the output, add a read-only field:
#     project_name = serializers.SerializerMethodField(read_only=True)

#     def get_project_name(self, obj):
#         return obj.project.project_name if obj.project else None

#     def get_created_by(self, obj):
#         return obj.created_by.username if obj.created_by else None

#     def get_modified_by(self, obj):
#         return obj.modified_by.username if obj.modified_by else None
    
#     def get_consumed_hours(self, obj):
#         return obj.consumed_hours

#     def get_remaining_hours(self, obj):
#         return obj.remaining_hours
#     assigned_to = serializers.PrimaryKeyRelatedField(
#         queryset=Account.objects.all(),
#         required=False,
#         allow_null=True
#     )

#     def to_representation(self, instance):
#         rep = super().to_representation(instance)
#         # Replace assigned_to with user object if present
#         if instance.assigned_to:
#             rep["assigned_to"] = {
#                 "id": instance.assigned_to.id,
#                 "username": instance.assigned_to.username
#             }
#         else:
#             rep["assigned_to"] = None
#         return rep

#     class Meta:
#         model = Task
#         fields = [
#             "id",
#             "title",
#             "allocated_hours",
#             "consumed_hours",
#             "remaining_hours",
#             "allocated_hours",
#             "assigned_to",
#             "project",
#             "created_by",
#             "modified_by",
#             "status",
#             "project_name",
#         ]
class TaskSerializer(serializers.ModelSerializer):
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

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "allocated_hours",
            "consumed_hours",
            "remaining_hours",
            "assigned_to",
            "project",
            "project_name",
            "created_by",
            "modified_by",
        ]
        read_only_fields = [
            "created_by",
            "modified_by",
            "consumed_hours",
            "remaining_hours",
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
