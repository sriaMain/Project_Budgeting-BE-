from django.urls import path, include
from .views import ProjectAPIView, ProjectBudgetAPIView, TaskAPIView, TimesheetAPIView, TimesheetEntryAPIView, SubmitTimesheetAPIView

urlpatterns = [
    path('projects/', ProjectAPIView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/', ProjectAPIView.as_view(), name='project-detail'),
    path('projects/<int:project_no>/budget/', ProjectBudgetAPIView.as_view(), name='project-budget-detail'),
    path('budgets/<int:project_no>/', ProjectBudgetAPIView.as_view(), name='project-budget-detail-by-id'),
    path('budgets/', ProjectBudgetAPIView.as_view(), name='project-budget-list-create'),
    path('projects/<int:project_id>/budget/', ProjectBudgetAPIView.as_view()),
    path('tasks/', TaskAPIView.as_view(), name='task-list-create'),
    path('tasks/<int:task_id>/', TaskAPIView.as_view(), name='task-detail'),
    path('timesheet/', TimesheetAPIView.as_view(), name='timesheet-list-create'),
    path('timesheet/entry/', TimesheetEntryAPIView.as_view(), name='timesheet-entry-list-create'),
    path('timesheet/submit/', SubmitTimesheetAPIView.as_view(), name='submit-timesheet'),

]