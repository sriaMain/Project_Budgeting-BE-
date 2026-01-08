from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from urllib3 import request
from .models import Project, ProjectBudget, Task, Timesheet, TimesheetEntry, TaskTimerLog, TaskExtraHoursRequest
from .serializers import (ProjectCreateSerializer, ProjectBudgetSerializer, TaskSerializer,
 TimesheetEntrySerializer, TimesheetSerializer, TaskTimerLogSerializer, 
 TaskExtraHoursRequestSerializer, TaskExtraHoursReviewSerializer, ProjectListSerializer)
from accounts.models import Account
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from django.db.models import F
from django.shortcuts import get_object_or_404
from .tasks import send_task_assignment_email
from .utils import format_seconds

from datetime import timedelta, datetime


class ProjectAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # CREATE PROJECT
    # @transaction.atomic
    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()

        return Response(
            {
                "message": "Project created successfully",
                "project": ProjectCreateSerializer(project).data
            },
            status=status.HTTP_201_CREATED
        )
    
    def get(self, request, project_id=None):

        # 🔹 Single project
        if project_id:
            try:
                project = (
                    Project.objects
                    .select_related("client", "budget")
                    .get(project_no=project_id)
                )
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_200_OK
            )

        # 🔹 Query params
        search = request.query_params.get("search", "").strip()
        status_param = request.query_params.get("status", "").strip()
        budget_param = request.query_params.get("budget", "").strip()

        # 🔹 Base queryset (IMPORTANT)
        projects = Project.objects.select_related("client", "budget")

        # 🔹 Filters
        if search:
            projects = projects.filter(project_name__icontains=search)

        if status_param:
            projects = projects.filter(status__icontains=status_param)

        if budget_param:
            projects = projects.filter(
                Q(budget__total_budget__icontains=budget_param) |
                Q(budget__currency__icontains=budget_param)
            )

        # 🔹 Group by company
        company_map = {}

        for project in projects:
            client = project.client
            company_name = client.company_name if client else "No Client"

            if company_name not in company_map:
                company_map[company_name] = {
                    "company_name": company_name,
                    "total_projects": 0,
                    "project_details": []
                }

            company_map[company_name]["project_details"].append(
                ProjectListSerializer(project).data
            )
            company_map[company_name]["total_projects"] += 1

        return Response(
            {"Projects": list(company_map.values())},
            status=status.HTTP_200_OK
        )



    # def get(self, request, project_id=None):
    #     if project_id:
    #         try:
    #             project = Project.objects.get(project_no=project_id)
    #         except Project.DoesNotExist:
    #             return Response(
    #                 {"error": "Project not found"},
    #                 status=status.HTTP_404_NOT_FOUND
    #             )

    #         return Response(
    #             ProjectListSerializer(project).data,
    #             status=status.HTTP_200_OK
    #         )

    #     # Accept both 'search' and common typo 'serach' as query param
    #     search = request.GET.get('search', '').strip()
    #     if not search:
    #         search = request.GET.get('serach', '').strip()
    #     status_param = request.GET.get('status', '').strip()
    #     budget_param = request.GET.get('budget', '').strip()
    #     projects = Project.objects.select_related('client', 'budget').all()
    #     # If only status is provided, filter only by status
    #     if status_param and not search and not budget_param:
    #         projects = projects.filter(status__icontains=status_param)
    #     else:
    #         # Filter by project_name (search)
    #         if search:
    #             projects = projects.filter(project_name__icontains=search)
    #         # Filter by status
    #         if status_param:
    #             projects = projects.filter(status__icontains=status_param)
    #         # Filter by budget fields (total_budget or currency)
    #         if budget_param:
    #             from django.db.models import Q
    #             # Always filter by string match on total_budget and currency
    #             projects = projects.filter(
    #                 Q(budget__total_budget__isnull=False) & Q(budget__total_budget__icontains=budget_param)
    #                 | Q(budget__currency__icontains=budget_param)
    #             )
    #     # from .serializers import ProjectListSerializer  # Already imported at the top
    #     company_map = {}
    #     for project in projects:
    #         client_name = project.client.company_name if project.client else "No Client"
    #         if client_name not in company_map:
    #             company_map[client_name] = {
    #                 "company_name": client_name,
    #                 "total_projects": 0,
    #                 "project_details": []
    #             }
    #         company_map[client_name]["project_details"].append(ProjectListSerializer(project).data)
    #         company_map[client_name]["total_projects"] += 1
    #     # Return as a list under the key 'Projects'
    #     result = {"Projects": list(company_map.values())}
    #     return Response(result, status=status.HTTP_200_OK)
    # UPDATE PROJECT

    def put(self, request, project_id):
        try:
            project = Project.objects.get(project_no=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ProjectCreateSerializer(
            project,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        project = serializer.save()

        return Response(
            {
                "message": "Project updated successfully",
                "project": ProjectCreateSerializer(project).data
            },
            status=status.HTTP_200_OK
        )

    # DELETE PROJECT
    # @transaction.atomic
    def delete(self, request, project_id):
        try:
            project = Project.objects.get(project_no=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        project.delete()
        return Response(
            {"message": "Project deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


class ProjectBudgetCRUDAPIView(APIView):
    permission_classes = [IsAuthenticated]

    # CREATE / UPDATE BUDGET
    # @transaction.atomic
    def post(self, request, project_id):
        try:
            project = Project.objects.get(project_no=project_id)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        budget, created = ProjectBudget.objects.get_or_create(project=project)

        serializer = ProjectBudgetSerializer(
            budget,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        budget = serializer.save()

        if budget.use_quoted_amounts:
            budget.apply_quoted_amounts()
            budget.save()

        return Response(
            {
                "message": "Project budget saved successfully",
                "budget": ProjectBudgetSerializer(budget).data
            },
            status=status.HTTP_200_OK
        )

    # READ BUDGET
    def get(self, request, project_id):
        try:
            budget = ProjectBudget.objects.get(project__project_no=project_id)
        except ProjectBudget.DoesNotExist:
            return Response(
                {"error": "Budget not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            ProjectBudgetSerializer(budget).data,
            status=status.HTTP_200_OK
        )

    # DELETE BUDGET
    # @transaction.atomic
    def delete(self, request, project_id):
        try:
            budget = ProjectBudget.objects.get(project__project_no=project_id)
        except ProjectBudget.DoesNotExist:
            return Response(
                {"error": "Budget not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        budget.delete()
        return Response(
            {"message": "Budget deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


class ProjectBudgetAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # CREATE / UPDATE BUDGET
    # @transaction.atomic
    def post(self, request, project_no):
        try:
            project = Project.objects.get(project_no=project_no)
        except Project.DoesNotExist:
            return Response(
                {"error": "Project not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        budget, created = ProjectBudget.objects.get_or_create(project=project)

        serializer = ProjectBudgetSerializer(
            budget,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)

        budget = serializer.save()

        if budget.use_quoted_amounts:
            budget.apply_quoted_amounts()
            budget.save()

        return Response(
            {
                "message": "Project budget saved successfully",
                "budget": ProjectBudgetSerializer(budget).data
            },
            status=status.HTTP_200_OK
        )

    # READ BUDGET
    def get(self, request, project_no):
        try:
            budget = ProjectBudget.objects.get(project__project_no=project_no)
        except ProjectBudget.DoesNotExist:
            return Response(
                {"error": "Budget not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            ProjectBudgetSerializer(budget).data,
            status=status.HTTP_200_OK
        )

    # DELETE BUDGET
    # @transaction.atomic
    def delete(self, request, project_no):
        try:
            budget = ProjectBudget.objects.get(project__project_no=project_no)
        except ProjectBudget.DoesNotExist:
            return Response(
                {"error": "Budget not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        budget.delete()
        return Response(
            {"message": "Budget deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

from django.shortcuts import get_object_or_404
class TaskAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # CREATE TASK
    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(created_by=request.user)

        # Notify assignee if provided
        if task.assigned_to_id:
            send_task_assignment_email.delay(task.id, task.assigned_to_id)

        return Response(
            {
                "message": "Task created successfully",
                "task": TaskSerializer(task).data
            },
            status=status.HTTP_201_CREATED
        )




    def get(self, request, task_id=None, project_id=None):
        user = request.user

        is_employee = user.roles.filter(role_name="Employee").exists()
        is_manager = user.roles.filter(role_name__in=["Manager", "Project Manager"]).exists()
        is_admin = user.roles.filter(role_name="Admin").exists()

        # 🔹 Task detail
        if task_id:
            from .models import Task
            task = get_object_or_404(Task.objects.prefetch_related('time_entries'), id=task_id)

            # Employee can only view assigned task
            if is_employee and task.assigned_to != user:
                return Response(
                    {"error": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Debug: print if assigned or not
            print(f"DEBUG: Task ID {task.id} assigned_to: {task.assigned_to}")
            if task.assigned_to:
                print(f"DEBUG: Task is assigned to user ID {task.assigned_to.id}")
            else:
                print("DEBUG: Task is not assigned to any user.")

            # return Response(TaskSerializer(task).data)
            return Response(
                    TaskSerializer(task, context={"request": request}).data
    )


        # 🔹 Task list
        from .models import Task
        if is_admin or is_manager:
            tasks = Task.objects.prefetch_related('time_entries').all()
        elif is_employee:
            tasks = Task.objects.prefetch_related('time_entries').filter(assigned_to=user)
        else:
            tasks = Task.objects.none()

        # Group tasks by project for all cases
        from .redis_utils import get_active_timer
        def add_live_timer_fields(task, user, request):
            data = TaskSerializer(task, context={"request": request}).data
            redis_task, redis_start = get_active_timer(user.id)
            consumed_hours = float(data["consumed_hours"])
            allocated_hours = float(data["allocated_hours"])
            if redis_task and int(redis_task) == task.id:
                from django.utils import timezone
                start_time = timezone.datetime.fromisoformat(redis_start.decode())
                elapsed_seconds = int((timezone.now() - start_time).total_seconds())
                running_hours = elapsed_seconds / 3600
                consumed_hours += running_hours
                data["consumed_hours"] = consumed_hours
                data["remaining_hours"] = max(allocated_hours - consumed_hours, 0)
            # Calculate needs_extra_hours using the possibly updated consumed_hours
            data["needs_extra_hours"] = consumed_hours > allocated_hours
            return data

        def group_tasks_by_project(tasks, user, request):
            project_map = {}
            for task in tasks:
                project = task.project
                if not project:
                    continue
                project_id = project.project_no
                project_name = project.project_name
                if project_id not in project_map:
                    project_map[project_id] = {
                        "project_name": project_name,
                        "project_no": project_id,
                        "Tasks": []
                    }
                # Add full task details with live timer values if running
                task_data = add_live_timer_fields(task, user, request)
                project_map[project_id]["Tasks"].append(task_data)
            return list(project_map.values())

        # If project_id is provided, filter tasks accordingly
        if project_id:
            if is_admin or is_manager:
                tasks = Task.objects.prefetch_related('time_entries').filter(project_id=project_id)
            elif is_employee:
                tasks = Task.objects.prefetch_related('time_entries').filter(project_id=project_id, assigned_to=user)
            else:
                tasks = Task.objects.none()

        grouped = group_tasks_by_project(tasks, user, request)
        return Response(
            grouped,
            status=status.HTTP_200_OK
        )
    def put(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"},
                status=404
            )

        # Only PM / Admin can assign
        if not request.user.roles.filter(
            role_name__in=["Project Manager", "Admin","Employee"]
        ).exists():
            return Response(
                {"error": "Permission denied"},
                status=403
            )

        assigned_to = request.data.get("assigned_to")

        if not assigned_to:
            return Response(
                {"error": "assigned_to is required"},
                status=400
            )

        user = Account.objects.get(id=assigned_to)

        # 🔒 SAFETY CHECK: user must belong to same service as task creator (optional)
        # if user.module != task.project.service:
        #     return Response({"error": "User does not belong to selected service"}, status=400)

        task.assigned_to = user
        task.status = "planned"
        task.save()

        return Response({
            "message": "Task assigned successfully",
            "task_id": task.id,
            "assigned_to": {
                "id": user.id,
                "name": user.get_full_name(),
                "service": user.module.product_service_name if user.module else None
            }
        })
    def patch(self, request, task_id):
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"},
                status=404
            )

        # Only PM / Admin / Employee can update
        if not request.user.roles.filter(
            role_name__in=["Project Manager", "Admin", "Employee"]
        ).exists():
            return Response(
                {"error": "Permission denied"},
                status=403
            )

        print("PATCH request.data:", request.data)

        # 🔒 Block status change from in_progress back to planned (unless hours exceeded)
        requested_status = request.data.get("status")
        if requested_status and requested_status == 'planned' and task.status == 'in_progress':
            # Check if this task has an active timer
            has_active = TaskTimerLog.objects.filter(task=task, is_active=True).exists()
            if has_active:
                return Response(
                    {
                        "error": "Cannot change status to planned while timer is running",
                        "message": "Stop the timer before changing status back to planned"
                    },
                    status=400
                )
            # If no active timer, check if hours are exceeded
            consumed = float(task.consumed_hours)
            allocated = float(task.allocated_hours)
            if consumed <= allocated:
                # Hours NOT exceeded; block the status change
                return Response(
                    {
                        "error": "Cannot change status to planned while in progress",
                        "message": "Task must be completed or moved to needs_attention before returning to planned"
                    },
                    status=400
                )
            # Hours ARE exceeded; allow the change

        old_assigned_to = task.assigned_to_id
        serializer = TaskSerializer(task, data=request.data, partial=True)
        if not serializer.is_valid():
            print("PATCH serializer.errors:", serializer.errors)
            return Response({"errors": serializer.errors}, status=400)
        serializer.save()

        new_assigned_to = serializer.instance.assigned_to_id
        if new_assigned_to and new_assigned_to != old_assigned_to:
            send_task_assignment_email.delay(task.id, new_assigned_to)

        return Response({
            "message": "Task updated successfully (partial)",
            "task": serializer.data
        }, status=200)

    def delete(self, request, task_id):
            try:
                task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                return Response(
                    {"error": "Task not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            task.delete()
            return Response(
                {"message": "Task deleted successfully"},
                status=status.HTTP_204_NO_CONTENT
            )


class ServiceUsersAPIView(APIView):
    # permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from product_group.models import Product_Services

        services = Product_Services.objects.filter(is_active=True)
        result = []
        for service in services:
            users = Account.objects.filter(module=service, is_active=True)
            result.append({
                "product_services": service.product_service_name,
                "users": [
                    {'id': u.id, "username": u.username} for u in users
                ]
            })
        return Response(result)




# Project/views.py

from .serializers import TimesheetSerializer
from .utils import get_week_range

class TimesheetAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Support optional week_start query param (YYYY-MM-DD). Defaults to current week (Sun–Sat)
        week_start_str = request.query_params.get('week_start')
        include_orphans = request.query_params.get('include_orphans') in {"1", "true", "True", "yes"}
        if week_start_str:
            try:
                provided = datetime.strptime(week_start_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({"error": "Invalid week_start format. Use YYYY-MM-DD"}, status=400)
            week_start, week_end = get_week_range(provided)
        else:
            today = timezone.now().date()
            week_start, week_end = get_week_range(today)

        # Prefer an existing timesheet that overlaps this Sun–Sat week to avoid creating a duplicate
        timesheet = Timesheet.objects.filter(
            user=request.user,
            week_start__lte=week_end,
            week_end__gte=week_start,
        ).order_by('week_start').first()

        if not timesheet:
            timesheet, _ = Timesheet.objects.get_or_create(
                user=request.user,
                week_start=week_start,
                defaults={'week_end': week_end}
            )
        elif timesheet.week_end != week_end:
            timesheet.week_end = week_end
            timesheet.save(update_fields=["week_end"])

        # Only assigned tasks for employee
        tasks = Task.objects.filter(assigned_to=request.user)

        return Response({
            "timesheet": TimesheetSerializer(
                timesheet,
                context={"week_start": week_start, "week_end": week_end, "include_orphans": include_orphans}
            ).data,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "allocated_hours": float(task.allocated_hours),
                    "consumed_hours": float(task.consumed_hours),
                    "remaining_hours": float(task.remaining_hours),
                } for task in tasks
            ]
        })



class TimesheetEntryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]


    def get(self, request):
        entries = TimesheetEntry.objects.filter(
            timesheet__user=request.user,
            timesheet__status='draft'
        )

        return Response(
            TimesheetEntrySerializer(entries, many=True).data
        )




    def post(self, request):
        task_id = request.data.get("task")
        date = request.data.get("date")
        hours = request.data.get("hours")

        if not task_id or not date or hours is None:
            return Response(
                {"error": "Task, date and hours are required"},
                status=400
            )

        hours = Decimal(str(hours))
        entry_date = timezone.datetime.fromisoformat(date).date()

        # 🔹 Get task
        task = Task.objects.get(id=task_id)

        # 🔹 Week calculation
        week_start, week_end = get_week_range(entry_date)

        # 🔹 Get or create timesheet
        timesheet, _ = Timesheet.objects.get_or_create(
            user=request.user,
            week_start=week_start,
            defaults={"week_end": week_end}
        )

        if timesheet.status != "draft":
            return Response(
                {"error": "Timesheet already submitted"},
                status=400
            )

        # 🔹 Role checks
        is_employee = request.user.roles.filter(role_name="Employee").exists()
        is_manager = request.user.roles.filter(
            role_name__in=["Manager", "Project Manager", "Admin"]
        ).exists()

        # ==========================================================
        # 1️⃣ DAILY MAX HOURS (8 hrs)
        # ==========================================================
        daily_hours = task.time_entries.filter(
            timesheet__user=request.user,
            date=entry_date
        ).exclude(date=entry_date).aggregate(
            total=Sum("hours")
        )["total"] or Decimal("0")

        if is_employee and (daily_hours + hours) > Decimal("8"):
            return Response(
                {"error": "Daily limit exceeded (max 8 hours)"},
                status=400
            )

        # ==========================================================
        # 2️⃣ WEEKLY MAX HOURS (40 hrs)
        # ==========================================================
        weekly_hours = TimesheetEntry.objects.filter(
            timesheet=timesheet
        ).exclude(date=entry_date).aggregate(
            total=Sum("hours")
        )["total"] or Decimal("0")

        if is_employee and (weekly_hours + hours) > Decimal("40"):
            return Response(
                {"error": "Weekly limit exceeded (max 40 hours)"},
                status=400
            )

        # ==========================================================
        # 3️⃣ TASK ALLOCATED HOURS CHECK
        # ==========================================================
        task_logged = task.time_entries.filter(
            timesheet__user=request.user
        ).exclude(date=entry_date).aggregate(
            total=Sum("hours")
        )["total"] or Decimal("0")

        total_task_hours = task_logged + hours

        if is_employee and total_task_hours > task.allocated_hours:
            return Response(
                {
                    "error": "Allocated hours exceeded",
                    "allocated_hours": task.allocated_hours,
                    "attempted_total": total_task_hours
                },
                status=400
            )

        # ==========================================================
        # SAVE ENTRY
        # ==========================================================
        TimesheetEntry.objects.update_or_create(
            timesheet=timesheet,
            task=task,
            date=entry_date,
            defaults={"hours": hours}
        )

        # ==========================================================
        # 4️⃣ WARNING AT 80% USAGE (NON-BLOCKING)
        # ==========================================================
        usage_percent = (total_task_hours / task.allocated_hours) * 100
        warning = None

        if usage_percent >= 80:
            warning = f"Warning: {int(usage_percent)}% of allocated hours used"

        return Response({
            "message": "Time entry saved",
            "daily_total": daily_hours + hours,
            "weekly_total": weekly_hours + hours,
            "task_used": total_task_hours,
            "remaining_hours": max(task.allocated_hours - total_task_hours, 0),
            "warning": warning
        })
class SubmitTimesheetAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, timesheet_id):
        timesheet = Timesheet.objects.get(
            id=timesheet_id,
            user=request.user,
            status='draft'
        )

        timesheet.status = 'submitted'
        timesheet.submitted_at = timezone.now()
        timesheet.save()

        return Response({"message": "Timesheet submitted successfully"})



from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .redis_utils import seconds_to_hms, set_active_timer

from .redis_utils import has_active_timer, set_active_timer

def seconds_to_hms(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class StartTaskTimerAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # def post(self, request, task_id):
    #     user = request.user

    #     try:
    #         task = Task.objects.get(id=task_id)
    #     except Task.DoesNotExist:
    #         return Response(
    #             {"error": "Task not found"},
    #             status=404
    #         )

    #     # 🔐 PERMISSION CHECK (CRITICAL)
    #     if user.is_staff:
    #         return Response(
    #             {"error": "Admins are not allowed to start task timers"},
    #             status=403
    #         )

    #     if task.assigned_to_id != user.id:
    #         return Response(
    #             {"error": "You are not assigned to this task"},
    #             status=403
    #         )


    #     # 🚫 Restriction removed: allow multiple start/stop cycles for a task timer

    #     # ⏱ Check if another timer is already running
    #     if has_active_timer(user.id):
    #         running_task_id, running_start = get_active_timer(user.id)

    #         running_task = None
    #         if running_task_id:
    #             try:
    #                 running_task = Task.objects.get(id=int(running_task_id))
    #             except Task.DoesNotExist:
    #                 pass

    #         if int(running_task_id) == task.id:
    #             return Response(
    #                 {
    #                     "error": "Timer is already running for this task. Please pause or stop it before starting again.",
    #                     "running_task": {
    #                         "id": int(running_task_id),
    #                         "title": running_task.title if running_task else None,
    #                         "started_at": running_start.decode() if running_start else None,
    #                     },
    #                     "action": "pause_or_stop"
    #                 },
    #                 status=400
    #             )
    #         else:
    #             return Response(
    #                 {
    #                     "error": "Another timer is already running",
    #                     "running_task": {
    #                         "id": int(running_task_id),
    #                         "title": running_task.title if running_task else None,
    #                         "started_at": running_start.decode() if running_start else None,
    #                     },
    #                     "action": "switch_task"
    #                 },
    #                 status=400
    #             )

    #     # ▶️ START TIMER
    #     timer = TaskTimerLog.objects.create(
    #         task=task,
    #         user=user,
    #         start_time=timezone.now(),
    #         is_active=True
    #     )

    #     set_active_timer(user.id, task.id, timer.start_time)

    #     # Calculate previously worked seconds for this task and user
    #     previous_logs = TaskTimerLog.objects.filter(task=task, user=user, is_active=False)
    #     prev_seconds = sum([(log.end_time - log.start_time).total_seconds() for log in previous_logs if log.end_time and log.start_time])
    #     prev_seconds = int(prev_seconds)

    #     # 🔥 WebSocket Event
    #     channel_layer = get_channel_layer()
    #     async_to_sync(channel_layer.group_send)(
    #         f"user_{user.id}",
    #         {
    #             "type": "timer_event",
    #             "data": {
    #                 "event": "TIMER_STARTED",
    #                 "task_id": task.id,
    #                 "started_at": timer.start_time.isoformat(),
    #                 "total_seconds": 0,
    #                 "running": True,
    #                 "previous_total_seconds": prev_seconds
    #             }
    #         }
    #     )

    #     return Response({"message": "Timer started successfully"})

    def post(self, request, task_id):
        user = request.user

        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)

        # 🔐 PERMISSION CHECK
        if user.is_staff:
            return Response(
                {"error": "Admins are not allowed to start task timers"},
                status=403
            )

        if task.assigned_to_id != user.id:
            return Response(
                {"error": "You are not assigned to this task"},
                status=403
            )

        # 🚫 Check if task was already stopped today
        today_logs = TaskTimerLog.objects.filter(
            task_id=task_id,
            user=user,
            is_active=False,
            end_time__date=timezone.now().date()
        )
        
        if today_logs.exists():
            # Check if timesheet entry exists (means it was stopped, not just paused)
            today = timezone.now().date()
            timesheet_exists = TimesheetEntry.objects.filter(
                timesheet__user=user,
                task_id=task_id,
                date=today
            ).exists()
            
            if timesheet_exists:
                return Response(
                    {
                        "error": "This task has already been stopped today and cannot be restarted.",
                        "message": "Task timer was stopped and logged to timesheet. You cannot restart a stopped task."
                    },
                    status=400
                )

        # ⏱ Check if another timer is already running
        if has_active_timer(user.id):
            running_task_id, running_start = get_active_timer(user.id)

            running_task = None
            if running_task_id:
                try:
                    running_task = Task.objects.get(id=int(running_task_id))
                except Task.DoesNotExist:
                    pass

            # ❌ Same task already running
            if int(running_task_id) == task.id:
                return Response(
                    {
                        "error": "Timer is already running for this task.",
                        "running_task": {
                            "id": int(running_task_id),
                            "title": running_task.title if running_task else None,
                            "started_at": running_start.decode() if running_start else None,
                        },
                        "action": "pause_or_stop"
                    },
                    status=400
                )

            # ❌ Another task running
            return Response(
                {
                    "error": "Another timer is already running",
                    "running_task": {
                        "id": int(running_task_id),
                        "title": running_task.title if running_task else None,
                        "started_at": running_start.decode() if running_start else None,
                    },
                    "action": "switch_task"
                },
                status=400
            )

        # ▶️ START / RESUME TIMER
        # 🔥 Check if allocated hours already exceeded
        allocated_hours = float(task.allocated_hours)
        consumed_hours = float(task.consumed_hours)
        
        if consumed_hours >= allocated_hours:
            # Check if there's a pending or approved extra hours request
            from .models import TaskExtraHoursRequest
            has_approved_extra = TaskExtraHoursRequest.objects.filter(
                task=task,
                status='approved'
            ).exists()
            
            if not has_approved_extra:
                return Response({
                    "error": "Cannot start timer: Allocated hours exceeded",
                    "message": "Task has consumed all allocated hours. Please request extra hours to continue.",
                    "allocated_hours": allocated_hours,
                    "consumed_hours": consumed_hours,
                    "action": "request_extra_hours"
                }, status=400)
        
        timer = TaskTimerLog.objects.create(
            task=task,
            user=user,
            start_time=timezone.now(),
            is_active=True
        )

        set_active_timer(user.id, task.id, timer.start_time)

        # 🟢 Auto-set task status to in_progress when timer starts
        if task.status != 'in_progress':
            task.status = 'in_progress'
            task.save(update_fields=["status", "modified_at"])

        # ✅ TOTAL TIME CALCULATION (FIXED)
        previous_logs = TaskTimerLog.objects.filter(
            task=task,
            user=user,
            is_active=False,
            end_time__isnull=False
        )

        prev_seconds = sum(
            (log.end_time - log.start_time).total_seconds()
            for log in previous_logs
        )
        prev_seconds = int(prev_seconds)
        total_seconds = prev_seconds


        # 🔥 WebSocket Event
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "timer_event",
                "data": {
                    "event": "TIMER_STARTED",  # start OR resume
                    "task_id": task.id,
                    "started_at": timer.start_time.isoformat(),
                    "total_seconds": prev_seconds,
                    "formatted_time": seconds_to_hms(total_seconds),
                    "running": True
                }
            }
        )

        return Response(
            {
                "message": "Timer started successfully",
                "task_id": task.id,
                "total_seconds": prev_seconds,
                "formatted_time": seconds_to_hms(total_seconds),
                "running": True
            }
        )



from .utils import get_week_range




from .redis_utils import clear_active_timer



class PauseTaskTimerAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, task_id):
        user = request.user

        timer = TaskTimerLog.objects.filter(
            task_id=task_id,
            user=user,
            is_active=True
        ).order_by('-start_time').first()

        if not timer:
            # Check if Redis has a running timer for this user
            redis_task, redis_start = get_active_timer(user.id)
            force_clear = request.query_params.get('force_clear')
            if redis_task:
                # There is a running timer in Redis, but not in DB
                if force_clear == '1':
                    clear_active_timer(user.id)
                    return Response({
                        "message": "Redis timer state force-cleared. You can now start a new timer."
                    })
                try:
                    running_task = Task.objects.get(id=int(redis_task))
                    running_title = running_task.title
                except Exception:
                    running_title = None
                return Response({
                    "error": "No active timer to pause for this task, but a timer is running for another task.",
                    "running_task": {
                        "id": int(redis_task),
                        "title": running_title,
                        "started_at": redis_start.decode() if redis_start else None
                    },
                    "recovery": "If you want to force clear the running timer, call this endpoint with ?force_clear=1."
                }, status=400)
            else:
                return Response(
                    {"error": "No active timer to pause"},
                    status=400
                )

        end_time = timezone.now()
        elapsed_seconds = int(
            (end_time - timer.start_time).total_seconds()
        )

        timer.end_time = end_time
        timer.is_active = False
        timer.duration_minutes = elapsed_seconds // 60
        timer.save()

        # ✅ Clear redis timer state so user can resume later
        clear_active_timer(user.id)

        # 🔥 Calculate accumulated time from previous logs
        from Project.models import Task
        task = Task.objects.filter(id=task_id).first()
        if not task:
            return Response({"error": "Task not found."}, status=400)
        
        previous_logs = TaskTimerLog.objects.filter(
            task=task,
            user=user,
            is_active=False,
            end_time__isnull=False
        )
        prev_seconds = sum(
            (log.end_time - log.start_time).total_seconds()
            for log in previous_logs
        )
        prev_seconds = int(prev_seconds)

        # 🔥 WebSocket Event for timer paused
        from .utils import format_seconds as format_seconds_obj
        
        formatted_obj = format_seconds_obj(prev_seconds)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "timer_event",
                "data": {
                    "event": "TIMER_PAUSED",
                    "task_id": task.id,
                    "started_at": timer.start_time.isoformat() if timer.start_time else None,
                    "total_seconds": prev_seconds,
                    "session_seconds": elapsed_seconds,
                    "running": False,
                    "formatted_time": formatted_obj
                }
            }
        )

        # 🔥 Check if allocated hours exceeded and send alert
        consumed_hours = float(task.consumed_hours)
        allocated_hours = float(task.allocated_hours)
        
        if consumed_hours > allocated_hours:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "timer_event",
                    "data": {
                        "event": "HOURS_EXCEEDED",
                        "task_id": task.id,
                        "task_title": task.title,
                        "allocated_hours": allocated_hours,
                        "consumed_hours": consumed_hours,
                        "exceeded_by": round(consumed_hours - allocated_hours, 2),
                        "message": f"Task '{task.title}' has exceeded allocated hours"
                    }
                }
            )

        return Response({
            "message": "Timer paused",
            "worked_seconds": elapsed_seconds,
            "consumed_hours": consumed_hours,
            "remaining_hours": float(task.remaining_hours),
            "total_seconds": prev_seconds,
            "formatted_time": seconds_to_hms(prev_seconds),
            "running": False
        })


class StopTaskTimerAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, task_id):
        user = request.user

        # Get ALL inactive logs for this task today
        timer_logs = TaskTimerLog.objects.filter(
            task_id=task_id,
            user=user,
            is_active=False,
            end_time__date=timezone.now().date()
        )

        if not timer_logs.exists():
            return Response(
                {"error": "No timer data to stop"},
                status=400
            )

        # ✅ Total duration in seconds (duration_minutes already stored in minutes)
        total_minutes_today = timer_logs.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        total_seconds_today = int(total_minutes_today * 60)

        # -------------------------------
        # CAP LOGGING TO ALLOCATED HOURS (NO EXTRA UNTIL APPROVAL)
        # -------------------------------
        # Compute prior worked seconds (before today) for this task/user
        prior_logs = TaskTimerLog.objects.filter(
            task_id=task_id,
            user=user,
            is_active=False,
            end_time__isnull=False,
        ).exclude(end_time__date=timezone.now().date())

        prior_seconds = 0
        for pl in prior_logs:
            if pl.start_time:
                prior_seconds += int((pl.end_time - pl.start_time).total_seconds())

        # Allocation window in seconds
        task_obj = Task.objects.get(id=task_id)
        allocated_seconds = int(float(task_obj.allocated_hours) * 3600)

        remaining_allowance_seconds = max(allocated_seconds - prior_seconds, 0)
        seconds_to_add = min(total_seconds_today, remaining_allowance_seconds)

        hours_to_add = Decimal(seconds_to_add) / Decimal("3600")
        extra_seconds_pending = max(total_seconds_today - seconds_to_add, 0)

        # -------------------------------
        # FLAG TODAY'S LOGS AS EXTRA IF BEYOND ALLOCATION
        # -------------------------------
        # Classify today's logs based on remaining allowance
        remaining_for_logs = remaining_allowance_seconds
        for log in timer_logs.order_by('start_time'):
            # Ensure we compute per-log duration accurately
            if not log.start_time or not log.end_time:
                continue
            log_seconds = int((log.end_time - log.start_time).total_seconds())
            if remaining_for_logs >= log_seconds:
                if log.is_extra:
                    log.is_extra = False
                    log.save(update_fields=['is_extra'])
                remaining_for_logs -= log_seconds
            else:
                if not log.is_extra:
                    log.is_extra = True
                    log.save(update_fields=['is_extra'])

        # -------------------------------
        # CREATE / UPDATE TIMESHEET ENTRY (ONLY ALLOWED PORTION)
        # -------------------------------
        entry_date = timezone.now().date()
        week_start = entry_date - timedelta(days=entry_date.weekday())
        week_end = week_start + timedelta(days=6)

        timesheet, _ = Timesheet.objects.get_or_create(
            user=user,
            week_start=week_start,
            defaults={"week_end": week_end}
        )

        entry, created = TimesheetEntry.objects.get_or_create(
            timesheet=timesheet,
            task_id=task_id,
            date=entry_date,
            defaults={"hours": hours_to_add}
        )

        if not created and hours_to_add > 0:
            entry.hours += hours_to_add
            entry.save()

        # ✅ Clear redis timer state so user can start a new timer
        clear_active_timer(user.id)

        # 🔥 Calculate accumulated time from previous logs
        from Project.models import Task
        task = Task.objects.get(id=task_id)
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
        prev_seconds = int(prev_seconds)

        allocated_hours = float(task.allocated_hours)
        allocated_seconds = int(allocated_hours * 3600)
        remaining_seconds = max(allocated_seconds - prev_seconds, 0)
        exceeded_by_seconds = max(prev_seconds - allocated_seconds, 0)

        # 🔥 WebSocket Event for task completed manually before exceeding time
        from .utils import format_seconds as format_seconds_obj
        formatted_total = format_seconds_obj(prev_seconds)
        formatted_remaining = format_seconds_obj(remaining_seconds)
        formatted_exceeded = format_seconds_obj(exceeded_by_seconds)

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "timer_event",
                "data": {
                    "event": "TASK_COMPLETED",
                    "task_id": task.id,
                    "is_stopped": True,
                    "stop_reason": "COMPLETED",
                    "stopped_at": timezone.now().isoformat(),
                    "allocated_hours": allocated_hours,
                    "total_seconds": prev_seconds,
                    "remaining_seconds": remaining_seconds,
                    "remaining_formatted": formatted_remaining["formatted"],
                    "formatted_time": formatted_total,
                    "running": False,
                    "message": "Task completed successfully before allocated time."
                }
            }
        )

        # 🔥 Check if allocated hours exceeded and send alert
        consumed_hours = float(entry.task.consumed_hours)
        
        if consumed_hours > allocated_hours:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "timer_event",
                    "data": {
                        "event": "HOURS_EXCEEDED",
                        "task_id": task.id,
                        "task_title": task.title,
                        "allocated_hours": allocated_hours,
                        "consumed_hours": consumed_hours,
                        "exceeded_by": round(consumed_hours - allocated_hours, 2),
                        "message": f"Task '{task.title}' has exceeded allocated hours"
                    }
                }
            )

        response_payload = {
            "message": "Timer stopped and timesheet updated",
            "logged_hours": round(hours_to_add, 2),
            "consumed_hours": consumed_hours,
            "remaining_hours": float(entry.task.remaining_hours),
        }

        # If there is extra beyond allocation, inform user it's pending approval
        if extra_seconds_pending > 0:
            response_payload.update({
                "extra_seconds_pending": extra_seconds_pending,
                "extra_hours_pending": round(Decimal(extra_seconds_pending) / Decimal("3600"), 2),
                "note": "Extra time beyond allocated is pending and not added to the timesheet. Submit an extra hours request for approval.",
                "action": "request_extra_hours"
            })

        return Response(response_payload)


# from django.utils import timezone
from .redis_utils import get_active_timer
from .redis_utils import seconds_to_hms

class TaskTimerStateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, task_id):
        user = request.user

        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response({"error": "No task found with this ID."}, status=404)

        redis_task, redis_start = get_active_timer(user.id)

        committed_consumed = float(task.consumed_hours)
        allocated_hours = float(task.allocated_hours)

        # ✅ CASE 1: THIS TASK IS RUNNING
        if redis_task and int(redis_task) == task_id:
            start_time = timezone.datetime.fromisoformat(redis_start.decode())
            elapsed_seconds = int((timezone.now() - start_time).total_seconds())

            running_hours = elapsed_seconds / 3600
            live_consumed = committed_consumed + running_hours
            live_remaining = max(allocated_hours - live_consumed, 0)

            hms = seconds_to_hms(elapsed_seconds)

            return Response({
                "status": "running",

                "task_id": task_id,
                "active_task_id": task_id,

                "has_active_timer": True,
                "is_current_task_running": True,

                # 🔥 BUTTON FLAGS
                "can_start": False,
                "can_pause": True,
                "can_stop": True,

                "elapsed_seconds": elapsed_seconds,
                "time": hms,
                "started_at": start_time,

                "allocated_hours": allocated_hours,
                "consumed_hours": round(live_consumed, 4),
                "remaining_hours": round(live_remaining, 4),
            })

        # ✅ CASE 2: SOME OTHER TASK IS RUNNING
        if redis_task and int(redis_task) != task_id:
            return Response({
                "status": "blocked",

                "task_id": task_id,
                "active_task_id": int(redis_task),

                "has_active_timer": True,
                "is_current_task_running": False,

                # 🔥 BUTTON FLAGS
                "can_start": False,
                "can_pause": False,
                "can_stop": False,

                "message": "Another task timer is already running",
            })

        # ✅ CASE 3: NO ACTIVE TIMER (PAUSED / FRESH)
        return Response({
            "status": "paused",

            "task_id": task_id,
            "active_task_id": None,

            "has_active_timer": False,
            "is_current_task_running": False,

            # 🔥 BUTTON FLAGS
            "can_start": True,
            "can_pause": False,
            "can_stop": False,

            "allocated_hours": allocated_hours,
            "consumed_hours": committed_consumed,
            "remaining_hours": max(allocated_hours - committed_consumed, 0),
        })




from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

class RequestExtraHoursAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, task_id):
        def _parse_hours(value):
            from decimal import Decimal
            from decimal import ROUND_HALF_UP
            if value is None:
                raise ValueError("requested_hours is required")
            # Already numeric
            if isinstance(value, (int, float, Decimal)):
                return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            # String formats
            if isinstance(value, str):
                if ":" in value:
                    parts = value.split(":")
                    if len(parts) not in (2, 3):
                        raise ValueError("Use HH:MM or HH:MM:SS")
                    try:
                        h = int(parts[0])
                        m = int(parts[1])
                        s = int(parts[2]) if len(parts) == 3 else 0
                    except Exception:
                        raise ValueError("Invalid time components; use numbers")
                    total_seconds = h * 3600 + m * 60 + s
                    return (Decimal(total_seconds) / Decimal("3600")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                # plain decimal string
                return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            raise ValueError("Unsupported requested_hours format")

        try:
            # Validate task exists; return 404 instead of bubbling DoesNotExist
            task = Task.objects.select_related("assigned_to").get(id=task_id)

            # Employee must be assigned
            if task.assigned_to != request.user:
                return Response(
                    {"error": "You are not assigned to this task"},
                    status=403
                )

            # 🚫 Check if there's already a pending request for this task
            existing_pending = TaskExtraHoursRequest.objects.filter(
                task=task,
                requested_by=request.user,
                status="pending"
            ).exists()

            if existing_pending:
                return Response(
                    {
                        "error": "You already have a pending extra hours request for this task",
                        "message": "Please wait for approval or rejection before submitting another request"
                    },
                    status=400
                )

            data = request.data.copy()
            try:
                parsed_hours = _parse_hours(data.get("requested_hours"))
            except ValueError as exc:
                return Response({"error": str(exc)}, status=400)
            data["requested_hours"] = parsed_hours

            serializer = TaskExtraHoursRequestSerializer(data=data)
            serializer.is_valid(raise_exception=True)

            TaskExtraHoursRequest.objects.create(
                task=task,
                requested_by=request.user,
                requested_hours=serializer.validated_data["requested_hours"],
                reason=serializer.validated_data["reason"],
                # 🔥 STORE PREVIOUS HOURS
                previous_allocated_hours=task.allocated_hours
            )

            requested_hours = serializer.validated_data["requested_hours"]
            requested_seconds = int(float(requested_hours) * 3600)

            return Response(
                {
                    "message": "Extra hours request submitted",
                    "requested_hours": float(requested_hours),
                    "requested_formatted": format_seconds(requested_seconds)["formatted"],
                },
                status=201
            )
        except Task.DoesNotExist:
            return Response({"error": "Task not found"}, status=404)


class PendingExtraHoursAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Only PM / Admin
        if not request.user.roles.filter(
            role_name__in=["Project Manager", "Admin"]
        ).exists():
            return Response(status=403)

        requests = TaskExtraHoursRequest.objects.filter(status="pending")

        data = [
            {
                "id": r.id,
                "task": r.task.title,
                "task_id": r.task.id,
                "requested_by": r.requested_by.username,
                "requested_hours": r.requested_hours,
                "requested_formatted": format_seconds(int(float(r.requested_hours) * 3600))["formatted"],
                "reason": r.reason,
            }
            for r in requests
        ]

        return Response(data)






from django.utils import timezone

class ReviewExtraHoursAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, request_id):

        # Only PM / Admin
        if not request.user.roles.filter(
            role_name__in=["Project Manager", "Admin"]
        ).exists():
            return Response(status=403)

        req = TaskExtraHoursRequest.objects.get(id=request_id)

        serializer = TaskExtraHoursReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]

        if action == "approve":
            # 🔥 CALCULATE FINAL HOURS
            req.approved_allocated_hours = (
                req.previous_allocated_hours + req.requested_hours
            )

            # 🔥 UPDATE TASK
            req.task.allocated_hours = req.approved_allocated_hours
            req.task.save()

            req.status = "approved"
        else:
            req.status = "rejected"

        req.reviewed_by = request.user
        req.reviewed_at = timezone.now()
        req.save()

        return Response({
            "task": req.task.title,
            "previous_allocated_hours": req.previous_allocated_hours,
            "previous_allocated_formatted": format_seconds(int(float(req.previous_allocated_hours) * 3600))["formatted"] if req.previous_allocated_hours is not None else None,
            "requested_extra_hours": req.requested_hours,
            "requested_formatted": format_seconds(int(float(req.requested_hours) * 3600))["formatted"],
            "approved_allocated_hours": req.approved_allocated_hours,
            "approved_allocated_formatted": format_seconds(int(float(req.approved_allocated_hours) * 3600))["formatted"] if req.approved_allocated_hours is not None else None,
            "status": req.status
        })

class TaskStatusChoicesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        status_choices = [choice[0] for choice in Task.STATUS_CHOICES]
        return Response({"status_choices": status_choices})

from collections import defaultdict



class TaskGroupedByStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # 1️⃣ Define all possible statuses explicitly
        status_keys = dict(Task.STATUS_CHOICES).keys()

        # 2️⃣ Initialize response with count = 0
        response_data = {
            status: {
                "count": 0,
                "tasks": []
            }
            for status in status_keys
        }

        # 3️⃣ Fetch tasks (optimized)
        queryset = (
            Task.objects
            .select_related("project", "assigned_to", "created_by", "modified_by")
            .prefetch_related("time_entries")
        )

        # 4️⃣ Populate response
        for task in queryset:
            serialized = TaskSerializer(task).data
            response_data[task.status]["tasks"].append(serialized)
            response_data[task.status]["count"] += 1
            return Response(response_data)

        return Response(response_data)