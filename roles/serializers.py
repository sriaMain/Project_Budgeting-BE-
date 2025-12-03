


from rest_framework import serializers
from .models import PermissionCategory, Permission, Role


class PermissionBasicSerializer(serializers.ModelSerializer):
    """
    Minimal permission serializer for Role list
    """
    category = serializers.CharField(
        source="category.permission_category_name",
        read_only=True
    )

    class Meta:
        model = Permission
        fields = ["id", "code", "label", "category"]


class PermissionSerializer(serializers.ModelSerializer):
    """
    Full permission serializer (used in permission tree)
    """
    category = serializers.CharField(
        source="category.permission_category_name",
        read_only=True
    )

    class Meta:
        model = Permission
        fields = ["id", "code", "label", "category", "is_active"]




class PermissionCategorySerializer(serializers.ModelSerializer):
    """
    Serializer to return permissions grouped by category
    """
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = PermissionCategory
        fields = ["id", "permission_category_name", "permissions"]




class RoleWriteSerializer(serializers.ModelSerializer):
    """
    Accepts only permission IDs
    Used for create/update
    """
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.filter(is_active=True),
        required=False,
    )

    class Meta:
        model = Role
        fields = ["id", "role_name", "description", "is_active", "permissions"]

    def validate_role_name(self, value):
        """
        Case-insensitive role name validation
        Admin ≠ admin
        """
        name = value.strip()

        qs = Role.objects.filter(role_name__iexact=name)
        # Exclude current instance on update
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError("Role name already exists.")
        return name


class RoleListSerializer(serializers.ModelSerializer):
    """
    List endpoint:
    Show minimal nested permission objects
    """
    permissions = PermissionBasicSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = ["id", "role_name", "description", "is_active", "permissions"]


class RoleDetailSerializer(serializers.ModelSerializer):
    """
    Detailed endpoint:
    Full nested permission data
    """
    permissions = PermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "role_name",
            "description",
            "is_active",
            "permissions",
            "created_by",
            "modified_by",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["created_by", "modified_by", "created_at", "modified_at"]
