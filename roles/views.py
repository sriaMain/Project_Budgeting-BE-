from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import PermissionCategory, Permission, Role
from .serializers import (
    PermissionCategorySerializer,
    PermissionSerializer,
    RoleWriteSerializer,
    RoleListSerializer,
    RoleDetailSerializer,
)
from .permission import HasPermissionCode


# -------- Permissions tree (for UI left list) --------

class PermissionTreeView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]
    # permission_code = "roles.permissions.view"

    def get(self, request):
        categories = PermissionCategory.objects.get_structured_permissions()
        serializer = PermissionCategorySerializer(categories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PermissionFlatListView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]
    # permission_code = "roles.permissions.view"

    def get(self, request):
        perms = Permission.objects.filter(is_active=True).order_by("category__name", "label")
        serializer = PermissionSerializer(perms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------- Role List + Create --------

class RoleListCreateView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]

    def get(self, request):
        # self.permission_code = "roles.view"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)

        roles = Role.objects.filter(is_active=True)
        serializer = RoleListSerializer(roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        # self.permission_code = "roles.create"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = RoleWriteSerializer(data=request.data)
        if serializer.is_valid():
            role = serializer.save()
            return Response(RoleDetailSerializer(role).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------- Role Detail / Update / Delete --------

class RoleDetailView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]

    def get_object(self, pk):
        return get_object_or_404(Role, pk=pk)

    def get(self, request, pk):
        # self.permission_code = "roles.view"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)

        role = self.get_object(pk)
        serializer = RoleDetailSerializer(role)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        # self.permission_code = "roles.update"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)
 
        role = self.get_object(pk)
        serializer = RoleWriteSerializer(role, data=request.data)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(RoleDetailSerializer(updated).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        # self.permission_code = "roles.update"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)

        role = self.get_object(pk)
        serializer = RoleWriteSerializer(role, data=request.data, partial=True)
        if serializer.is_valid():
            updated = serializer.save(modified_by=request.user)
            return Response(RoleDetailSerializer(updated).data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # self.permission_code = "roles.delete"
        # if not self.check_permissions(request):
        #     return Response(status=status.HTTP_403_FORBIDDEN)

        role = self.get_object(pk)
        role.is_active = False
        role.save(update_fields=["is_active", "modified_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
