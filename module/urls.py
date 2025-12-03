from django.urls import path
from .views import ModuleListCreateView

urlpatterns = [
    path('modules/', ModuleListCreateView.as_view(), name='module-list-create'),    
    path('modules/<int:pk>/', ModuleListCreateView.as_view(), name='module-detail'),
]