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
        if project_id:
            try:
                project = Project.objects.get(project_no=project_id)
            except Project.DoesNotExist:
                return Response(
                    {"error": "Project not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                ProjectListSerializer(project).data,
                status=status.HTTP_200_OK
            )

        # Accept both 'search' and common typo 'serach' as query param
        search = request.GET.get('search', '').strip()
        if not search:
            search = request.GET.get('serach', '').strip()
        status_param = request.GET.get('status', '').strip()
        budget_param = request.GET.get('budget', '').strip()
        projects = Project.objects.select_related('client', 'budget').all()
        # If only status is provided, filter only by status
        if status_param and not search and not budget_param:
            projects = projects.filter(status__icontains=status_param)
        else:
            # Filter by project_name (search)
            if search:
                projects = projects.filter(project_name__icontains=search)
            # Filter by status
            if status_param:
                projects = projects.filter(status__icontains=status_param)
            # Filter by budget fields (total_budget or currency)
            if budget_param:
                from django.db.models import Q
                # Always filter by string match on total_budget and currency
                projects = projects.filter(
                    Q(budget__total_budget__isnull=False) & Q(budget__total_budget__icontains=budget_param)
                    | Q(budget__currency__icontains=budget_param)
                )
        # from .serializers import ProjectListSerializer  # Already imported at the top
        company_map = {}
        for project in projects:
            client_name = project.client.company_name if project.client else "No Client"
            if client_name not in company_map:
                company_map[client_name] = {
                    "company_name": client_name,
                    "total_projects": 0,
                    "project_details": []
                }
            company_map[client_name]["project_details"].append(ProjectListSerializer(project).data)
            company_map[client_name]["total_projects"] += 1
        # Return as a list under the key 'Projects'
        result = {"Projects": list(company_map.values())}
        return Response(result, status=status.HTTP_200_OK)
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


class TaskAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # CREATE TASK
    def post(self, request):
        serializer = TaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(created_by=request.user)

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

            return Response(TaskSerializer(task).data)

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
        def add_live_timer_fields(task, user):
            data = TaskSerializer(task).data
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

        def group_tasks_by_project(tasks, user):
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
                # Add full task details (including task_id, etc), with live timer values if running
                task_data = add_live_timer_fields(task, user)
                task_data["task_id"] = task.id
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

        grouped = group_tasks_by_project(tasks, user)
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
        serializer = TaskSerializer(task, data=request.data, partial=True)
        if not serializer.is_valid():
            print("PATCH serializer.errors:", serializer.errors)
            return Response({"errors": serializer.errors}, status=400)
        serializer.save()
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
        today = timezone.now().date()
        week_start, week_end = get_week_range(today)

        timesheet, _ = Timesheet.objects.get_or_create(
            user=request.user,
            week_start=week_start,
            defaults={'week_end': week_end}
        )

        # Only assigned tasks for employee
        tasks = Task.objects.filter(assigned_to=request.user)

        return Response({
            "timesheet": TimesheetSerializer(timesheet).data,
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

class StartTaskTimerAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        user = request.user

        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            return Response(
                {"error": "Task not found"},
                status=404
            )

        # 🔐 PERMISSION CHECK (CRITICAL)
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

        # ⏱ Check if another timer is already running
        if has_active_timer(user.id):
            running_task_id, running_start = get_active_timer(user.id)

            running_task = None
            if running_task_id:
                try:
                    running_task = Task.objects.get(id=int(running_task_id))
                except Task.DoesNotExist:
                    pass

            return Response(
                {
                    "error": "Another timer is already running",
                    "running_task": {
                        "id": int(running_task_id),
                        "title": running_task.title if running_task else None,
                        "started_at": running_start.decode() if running_start else None,
                    }
                },
                status=400
            )

        # ▶️ START TIMER
        timer = TaskTimerLog.objects.create(
            task=task,
            user=user,
            start_time=timezone.now(),
            is_active=True
        )

        set_active_timer(user.id, task.id, timer.start_time)

        # 🔥 WebSocket Event
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {
                "type": "timer_event",
                "data": {
                    "event": "TIMER_STARTED",
                    "task_id": task.id,
                    "started_at": timer.start_time.isoformat(),
                }
            }
        )

        return Response({"message": "Timer started successfully"})


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

        # --- Update timesheet entry (same as stop logic) ---
        from decimal import Decimal
        entry_date = end_time.date()
        week_start = entry_date - timedelta(days=entry_date.weekday())
        week_end = week_start + timedelta(days=6)
        timesheet, _ = Timesheet.objects.get_or_create(
            user=user,
            week_start=week_start,
            defaults={"week_end": week_end}
        )
        hours = Decimal(elapsed_seconds) / Decimal("3600")
        # Always ensure task and timesheet are not null
        from Project.models import Task
        task = Task.objects.filter(id=task_id).first()
        if not task:
            return Response({"error": "Task not found for timesheet entry update."}, status=400)
        entry, created = TimesheetEntry.objects.get_or_create(
            timesheet=timesheet,
            task=task,
            date=entry_date,
            defaults={"hours": hours}
        )
        if not created:
            entry.hours += hours
            entry.save()

        # ✅ Clear redis timer state so user can start a new timer
        clear_active_timer(user.id)

        return Response({
            "message": "Timer paused",
            "worked_seconds": elapsed_seconds,
            "consumed_hours": float(entry.task.consumed_hours),
            "remaining_hours": float(entry.task.remaining_hours),
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

        # ✅ Total duration in seconds
        total_seconds = timer_logs.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0

        hours = Decimal(total_seconds) / Decimal("60")

        # -------------------------------
        # CREATE / UPDATE TIMESHEET ENTRY
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
            defaults={"hours": hours}
        )

        if not created:
            entry.hours += hours
            entry.save()

        # ✅ Clear redis timer state so user can start a new timer
        clear_active_timer(user.id)

        return Response({
            "message": "Timer stopped and timesheet updated",
            "logged_hours": round(hours, 2),
            "consumed_hours": float(entry.task.consumed_hours),
            "remaining_hours": float(entry.task.remaining_hours),
        })


# from django.utils import timezone
from .redis_utils import get_active_timer
from .redis_utils import seconds_to_hms

class TaskTimerStateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

#     def get(self, request, task_id):
#         user = request.user
#         try:
#             task = Task.objects.get(id=task_id)
#         except Task.DoesNotExist:
#             return Response({"error": "No task found with this ID."}, status=404)

#         redis_task, redis_start = get_active_timer(user.id)

#         # Default committed values
#         committed_consumed = float(task.consumed_hours)
#         allocated_hours = float(task.allocated_hours)

#         if redis_task and int(redis_task) == task_id:
#             start_time = timezone.datetime.fromisoformat(
#                 redis_start.decode()
#             )

#             elapsed_seconds = int(
#                 (timezone.now() - start_time).total_seconds()
#             )

#             # 🔥 LIVE calculation (THIS IS THE FIX)
#             running_hours = elapsed_seconds / 3600
#             live_consumed = committed_consumed + running_hours
#             live_remaining = max(allocated_hours - live_consumed, 0)

#             hms = seconds_to_hms(elapsed_seconds)

#             return Response({
#                 "status": "running",
#                 "elapsed_seconds": elapsed_seconds,
#                 "time": hms,
#                 "started_at": start_time,
#                 "task_id": task_id,

#                 # DB values
#                 "allocated_hours": allocated_hours,

#                 # LIVE values (UI only)
#                 "consumed_hours": round(live_consumed, 4),
#                 "remaining_hours": round(live_remaining, 4),
#             })

#         # If not running → return committed DB values
#         return Response({
#             "status": "paused",
#             "task_id": task_id,
#             "allocated_hours": allocated_hours,
#             "consumed_hours": committed_consumed,
#             "remaining_hours": max(allocated_hours - committed_consumed, 0),
#         })

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
        task = Task.objects.get(id=task_id)

        # Employee must be assigned
        if task.assigned_to != request.user:
            return Response(
                {"error": "You are not assigned to this task"},
                status=403
            )

        serializer = TaskExtraHoursRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        TaskExtraHoursRequest.objects.create(
            task=task,
            requested_by=request.user,
            requested_hours=serializer.validated_data["requested_hours"],
            reason=serializer.validated_data["reason"],
            # 🔥 STORE PREVIOUS HOURS
            previous_allocated_hours=task.allocated_hours
        )

        return Response(
            {"message": "Extra hours request submitted"},
            status=201
        )


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
                "requested_by": r.requested_by.username,
                "requested_hours": r.requested_hours,
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
            "requested_extra_hours": req.requested_hours,
            "approved_allocated_hours": req.approved_allocated_hours,
            "status": req.status
        })

class TaskStatusChoicesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        status_choices = [choice[0] for choice in Task.STATUS_CHOICES]
        return Response({"status_choices": status_choices})
    

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