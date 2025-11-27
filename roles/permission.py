from rest_framework.permissions import BasePermission

class HasPermissionCode(BasePermission):
    """
    Custom DRF permission that checks if the requesting user
    has the specified permission code via their assigned roles.
    
    Usage:
        permission_classes = [IsAuthenticated, HasPermissionCode]
        permission_code = "roles.permissions.view" # Must be set on the view
    """

    def has_permission(self, request, view):
        code = getattr(view, "permission_code", None)
        
        # If no permission_code is set on the view, then this permission
        # class doesn't enforce anything, effectively allowing access.
        # This is a common pattern for optional permissions, but be careful.
        # For critical views, always define a permission_code.
        if not code:
            return True 

        user = request.user
        
        # Check if user is authenticated and active
        if not user or not user.is_authenticated or not user.is_active:
            return False

        # Superusers bypass all permission checks
        if getattr(user, "is_superuser", False):
            return True
        
        # If user is not superuser, check against their role permissions
        # Assumes the User model has the RBACUserMixin with has_role_permission
        return user.has_role_permission(code)