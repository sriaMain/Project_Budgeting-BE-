from django.urls import path, include
from .views import ProjectAPIView, ProjectBudgetAPIView

urlpatterns = [
    path('projects/', ProjectAPIView.as_view(), name='project-list-create'),
    path('projects/<int:project_id>/', ProjectAPIView.as_view(), name='project-detail'),
    path('projects/<int:project_no>/budget/', ProjectBudgetAPIView.as_view(), name='project-budget-detail'),
    path('budgets/<int:project_no>/', ProjectBudgetAPIView.as_view(), name='project-budget-detail-by-id'),
    path('budgets/', ProjectBudgetAPIView.as_view(), name='project-budget-list-create'),
    path('projects/<int:project_id>/budget/', ProjectBudgetAPIView.as_view()),
]