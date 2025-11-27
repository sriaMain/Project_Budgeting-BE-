from rest_framework import serializers
from .models import PermissionCategory, Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "label", "category", "is_active"]


class PermissionCategorySerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True)

    class Meta:
        model = PermissionCategory
        fields = ["id", " permission_category_name", "permissions"]

class RoleListSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.filter(is_active=True),
        required=False
    )

    class Meta:
        model = Role
        fields = ["id", "role_name", "description", "is_active", "permissions"]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Replace id list with nested Permission
        rep["permissions"] = [
            {
                "id": p.id,
                "code": p.code,
                "label": p.label,
                "category": p.category.permission_category_name,
            }
            for p in instance.permissions.all()
        ]
        return rep


class RoleWriteSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = Role
        fields = ["id", "role_name", "description", "is_active", "permissions"]

    def validate_role_name(self, value):
        role_name = value.strip()
        if Role.objects.filter(role_name__iexact=role_name).exists():
            raise serializers.ValidationError("Role name already exists.")
        return role_name



# class RoleListSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Role
#         fields = ["id", "name", "description", "is_active","permissions"]


class RoleDetailSerializer(serializers.ModelSerializer):
    permissions = PermissionSerializer(many=True)

    class Meta:
        model = Role
        fields = ["id", "role_name", "description", "is_active", "permissions"]
