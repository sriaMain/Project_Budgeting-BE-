from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from .models import Project, ProjectBudget, Task, Timesheet, TimesheetEntry
from .serializers import (ProjectCreateSerializer, ProjectBudgetSerializer, TaskSerializer,
 TimesheetEntrySerializer, TimesheetSerializer)
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum




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

    # READ PROJECT / LIST PROJECTS
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
                ProjectCreateSerializer(project).data,
                status=status.HTTP_200_OK
            )

        projects = Project.objects.all().order_by('-created_at')
        return Response(
            ProjectCreateSerializer(projects, many=True).data,
            status=status.HTTP_200_OK
        )

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



    def get(self, request, task_id=None):
        user = request.user

        is_employee = user.roles.filter(role_name="Employee").exists()
        is_manager = user.roles.filter(role_name__in=["Manager", "Project Manager"]).exists()
        is_admin = user.roles.filter(role_name="Admin").exists()

        # 🔹 Task detail
        if task_id:
            task = get_object_or_404(Task, id=task_id)

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
        if is_admin or is_manager:
            tasks = Task.objects.all()
        elif is_employee:
            tasks = Task.objects.filter(assigned_to=user)
        else:
            tasks = Task.objects.none()

        return Response(
            TaskSerializer(tasks, many=True).data,
            status=status.HTTP_200_OK
        )



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
                    "allocated_hours": task.allocated_hours
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

    # def post(self, request):
    #     task_id = request.data.get("task")
    #     date = request.data.get("date")
    #     hours = request.data.get("hours")

    #     if not date:
    #         return Response(
    #             {"error": "Date is required"},
    #             status=400
    #         )

    #     entry_date = timezone.datetime.fromisoformat(date).date()
    #     week_start, week_end = get_week_range(entry_date)

    #     # ✅ AUTO-CREATE TIMESHEET
    #     timesheet, _ = Timesheet.objects.get_or_create(
    #         user=request.user,
    #         week_start=week_start,
    #         defaults={"week_end": week_end}
    #     )

    #     if timesheet.status != "draft":
    #         return Response(
    #             {"error": "Timesheet already submitted"},
    #             status=400
    #         )

    #     task = Task.objects.get(id=task_id)

    #     is_employee = request.user.roles.filter(role_name="Employee").exists()
    #     is_manager = request.user.roles.filter(
    #         role_name__in=["Manager", "Project Manager", "Admin"]
    #     ).exists()

    #     # 🔒 Permission rules
    #     if is_employee and task.assigned_to != request.user:
    #         return Response(
    #             {"error": "Task not assigned to you"},
    #             status=403
    #         )

    #     TimesheetEntry.objects.update_or_create(
    #         timesheet=timesheet,
    #         task=task,
    #         date=entry_date,
    #         defaults={"hours": hours}
    #     )

    #     return Response({
    #         "message": "Time entry saved",
    #         "timesheet_id": timesheet.id
    #     })


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

