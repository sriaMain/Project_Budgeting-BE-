from django.urls import path
from .views import (
    PermissionTreeView,
    PermissionFlatListView,
    RoleListCreateView,
    RoleDetailView,
)

urlpatterns = [
    path("permissions/tree/", PermissionTreeView.as_view(), name="permission-tree"),
    path("permissions/", PermissionFlatListView.as_view(), name="permission-list"),

    path("roles/", RoleListCreateView.as_view(), name="role-list-create"),
    path("roles/<int:pk>/", RoleDetailView.as_view(), name="role-detail"),
]
