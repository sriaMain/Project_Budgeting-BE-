from django.shortcuts import render

# Create your views here.
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import PermissionCategory, Permission, Role
from .serializers import (
    PermissionCategorySerializer,
    PermissionSerializer,
    RoleWriteSerializer,
    RoleListSerializer,
    RoleDetailSerializer,
)
from .permission import HasPermissionCode
from django.core.cache import cache
from django.utils import timezone


# -------- Permissions tree (for UI left list) --------

# c

class PermissionTreeView(APIView):
    def get(self, request):
        cache_key = "permission_tree_v1"
        data = cache.get(cache_key)

        # ========== CACHE HIT ==========
        if data:
            response = Response(data)
            response['X-Cache'] = 'HIT'
            return response

        # ========== CACHE MISS - FETCH FROM DB ==========
        categories = PermissionCategory.objects.get_structured_permissions()
        serialized = PermissionCategorySerializer(categories, many=True).data

        cache.set(cache_key, serialized, timeout=3600)

        response = Response(serialized, status=status.HTTP_200_OK)
        response['X-Cache'] = 'MISS'
        return response


class CacheTestView(APIView):
    """Simple endpoint to demonstrate cache get/set behavior.

    - GET the endpoint: first request returns X-Cache: MISS and sets a short TTL
    - subsequent requests within the TTL return X-Cache: HIT
    """

    def get(self, request):
        cache_key = "cache_test_v1"
        value = cache.get(cache_key)

        if value:
            resp = Response({"cache_key": cache_key, "value": value, "status": "HIT"}, status=status.HTTP_200_OK)
            resp['X-Cache'] = 'HIT'
            return resp

        now = timezone.now().isoformat()
        # short timeout for easy testing
        cache.set(cache_key, now, timeout=30)
        resp = Response({"cache_key": cache_key, "value": now, "status": "MISS"}, status=status.HTTP_200_OK)
        resp['X-Cache'] = 'MISS'
        return resp
# class PermissionTreeView(APIView):
#     # permission_classes = [IsAuthenticated, HasPermissionCode]
#     # permission_code = "roles.permissions.view"

#     def get(self, request):
#         cache_key = "permission_tree_v1"
#         data = cache.get(cache_key)

#         if data:
#             return Response(data)

#         categories = PermissionCategory.objects.get_structured_permissions()
#         serialized = PermissionCategorySerializer(categories, many=True).data

#         cache.set(cache_key, serialized, timeout=3600)
#         return Response(serialized, status=status.HTTP_200_OK)


# class PermissionFlatListView(APIView):
#     # permission_classes = [IsAuthenticated, HasPermissionCode]
#     # permission_code = "roles.permissions.view"

#     def get(self, request):
#         perms = Permission.objects.filter(is_active=True).order_by("category__name", "label")
#         serializer = PermissionSerializer(perms, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

class PermissionFlatListView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]
    # permission_code = "roles.permissions.view"

    def get(self, request):
        perms = (
            Permission.objects.filter(is_active=True)
            .select_related("category")
            .order_by("category__permission_category_name", "label")
        )
        serializer = PermissionSerializer(perms, many=True)
        return Response(serializer.data)



# -------- Role List + Create --------

# class RoleListCreateView(APIView):
#     # permission_classes = [IsAuthenticated, HasPermissionCode]

#     def get(self, request):
#         # self.permission_code = "roles.view"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)

#         roles = Role.objects.filter(is_active=True)
#         serializer = RoleListSerializer(roles, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def post(self, request):
#         # self.permission_code = "roles.create"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)

#         serializer = RoleWriteSerializer(data=request.data)
#         if serializer.is_valid():
#             role = serializer.save()
#             return Response(RoleDetailSerializer(role).data, status=status.HTTP_201_CREATED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RoleListCreateView(APIView):
    # permission_classes = [IsAuthenticated, HasPermissionCode]

    # Method → permission mapping
    # permission_map = {
    #     "GET": "roles.view",
    #     "POST": "roles.create",
    # }
    permission_classes = [AllowAny]


    def get(self, request):
        cache_key = "roles_list_v1"
        data = cache.get(cache_key)

        # ========== CACHE HIT ==========
        if data:
            response = Response(data, status=status.HTTP_200_OK)
            response['X-Cache'] = 'HIT'
            return response

        roles = (
            Role.objects.filter(is_active=True)
            # .prefetch_related("permissions")
            .order_by("role_name")
        )

        serialized = RoleListSerializer(roles, many=True).data
        # Cache the serialized data (not the serializer class)
        cache.set(cache_key, serialized, timeout=3600)

        response = Response(serialized, status=status.HTTP_200_OK)
        response['X-Cache'] = 'MISS'
        return response

    def post(self, request):
        # permission_classes = [AllowAny]

        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        role = serializer.save()
        return Response(
            RoleDetailSerializer(role).data,
            status=status.HTTP_201_CREATED
        )

# -------- Role Detail / Update / Delete --------

# class RoleDetailView(APIView):
#     # permission_classes = [IsAuthenticated, HasPermissionCode]

#     def get_object(self, pk):
#         return get_object_or_404(Role, pk=pk)

#     def get(self, request, pk):
#         # self.permission_code = "roles.view"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)

#         role = self.get_object(pk)
#         serializer = RoleDetailSerializer(role)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def put(self, request, pk):
#         # self.permission_code = "roles.update"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)
 
#         role = self.get_object(pk)
#         serializer = RoleWriteSerializer(role, data=request.data)
#         if serializer.is_valid():
#             updated = serializer.save()
#             return Response(RoleDetailSerializer(updated).data, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def patch(self, request, pk):
#         # self.permission_code = "roles.update"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)

#         role = self.get_object(pk)
#         serializer = RoleWriteSerializer(role, data=request.data, partial=True)
#         if serializer.is_valid():
#             updated = serializer.save(modified_by=request.user)
#             return Response(RoleDetailSerializer(updated).data, status=status.HTTP_200_OK)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#     def delete(self, request, pk):
#         # self.permission_code = "roles.delete"
#         # if not self.check_permissions(request):
#         #     return Response(status=status.HTTP_403_FORBIDDEN)

#         role = self.get_object(pk)
#         role.is_active = False
#         role.save(update_fields=["is_active", "modified_at"])
#         return Response(status=status.HTTP_204_NO_CONTENT)


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, HasPermissionCode]

    permission_map = {
        "GET": "roles.view",
        "PUT": "roles.update",
        "PATCH": "roles.update",
        "DELETE": "roles.delete",
    }

    def get_object(self, pk):
        return get_object_or_404(
            Role.objects.prefetch_related("permissions"),
            pk=pk,
            is_active=True,
        )

    def get(self, request, pk):
        role = self.get_object(pk)
        return Response(
            RoleDetailSerializer(role).data,
            status=status.HTTP_200_OK
        )

    def put(self, request, pk):
        role = self.get_object(pk)
        serializer = RoleWriteSerializer(role, data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = serializer.save()
        return Response(
            RoleDetailSerializer(updated).data,
            status=status.HTTP_200_OK
        )

    def patch(self, request, pk):
        role = self.get_object(pk)
        serializer = RoleWriteSerializer(role, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        updated = serializer.save()
        return Response(
            RoleDetailSerializer(updated).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        role = self.get_object(pk)
        role.is_active = False
        role.modified_by = request.user
        role.save(update_fields=["is_active", "modified_by", "modified_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
