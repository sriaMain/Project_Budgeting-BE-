from django.urls import path, include
from .views import (ProjectAPIView, ProjectBudgetAPIView, TaskAPIView, TaskTimerStateAPIView,
 TimesheetAPIView, TimesheetEntryAPIView, SubmitTimesheetAPIView, StartTaskTimerAPIView,
  PauseTaskTimerAPIView, PendingExtraHoursAPIView, ReviewExtraHoursAPIView, RequestExtraHoursAPIView,
  TaskStatusChoicesView, ServiceUsersAPIView, TaskGroupedByStatusAPIView)

urlpatterns = [
    path('projects/', ProjectAPIView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/', ProjectAPIView.as_view(), name='project-detail'),
    path('projects/<int:project_no>/budget/', ProjectBudgetAPIView.as_view(), name='project-budget-detail'),
    path('budgets/<int:project_no>/', ProjectBudgetAPIView.as_view(), name='project-budget-detail-by-id'),
    path('budgets/', ProjectBudgetAPIView.as_view(), name='project-budget-list-create'),
    path('projects/<int:project_id>/budget/', ProjectBudgetAPIView.as_view()),
    path('tasks/<int:project_id>/tasks/', TaskAPIView.as_view(), name='project-tasks-list'),  #project related tasks
    path('tasks/', TaskAPIView.as_view(), name='task-list-create'),
    path('services/users/', ServiceUsersAPIView.as_view(), name='service-users-list'),
    path('tasks/<int:task_id>/', TaskAPIView.as_view(), name='task-detail'),
    path('timesheet/', TimesheetAPIView.as_view(), name='timesheet-list-create'),
    path('timesheet/entry/', TimesheetEntryAPIView.as_view(), name='timesheet-entry-list-create'),
    path('timesheet/submit/', SubmitTimesheetAPIView.as_view(), name='submit-timesheet'),
    path("tasks/<int:task_id>/timer/start/",StartTaskTimerAPIView.as_view()),#start task timer
    path("tasks/<int:task_id>/timer/pause/", PauseTaskTimerAPIView.as_view()), #pause task timer
    path("tasks/<int:task_id>/extra-hours/request/", RequestExtraHoursAPIView.as_view()), #request extra hours
    path("tasks/extra-hours/pending/",  PendingExtraHoursAPIView.as_view()), #view pending extra hours requests
    path("tasks/extra-hours/<request_id>/review/", ReviewExtraHoursAPIView.as_view()), #review extra hours requests
    path('task-status-choices/', TaskStatusChoicesView.as_view(), name='task-status-choices'), #get task status choices
    path('tasks/grouped-by-status/', TaskGroupedByStatusAPIView.as_view(), name='tasks-grouped-by-status'),
    path("tasks/<int:task_id>/timer/state/",TaskTimerStateAPIView.as_view(),name="task-timer-state"
    ),
    # path()
    
  

        

]