from django.db import models
from django.db.models import Prefetch
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models.functions import Lower
from django.core.cache import cache



# --- IMPORTANT ---
# All models are defined here, so top-level imports are fine for each other.
# This prevents circular import issues as long as your app's models are
# not trying to import something from another app's models that in turn
# imports from roles's models.


class PermissionCategoryManager(models.Manager):
    def get_structured_permissions(self):
        """
        For UI 'Available Permissions' list:
        2 queries total: categories + active permissions.
        """
        # Permission model is now defined in the same file, so direct reference is fine
        active_perms = Permission.objects.filter(is_active=True).order_by("label")

        return (
            self.get_queryset()
            .filter(permissions__is_active=True)
            .distinct()
            .prefetch_related(
                Prefetch("permissions", queryset=active_perms)
            )
        )




class PermissionCategory(models.Model):
    """Groups permissions in UI (User Management, Ticket, SLA, etc.)."""
    permission_category_name = models.CharField(max_length=150, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    objects = PermissionCategoryManager()

    class Meta:
        verbose_name_plural = "Permission Categories"
        ordering = ["permission_category_name"]

    def __str__(self):
        return self. permission_category_name


class Permission(models.Model):
    """Atomic actions, e.g. 'ticket.create', 'user.view'."""
    code = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Machine-readable code, e.g. 'ticket.create'",
    )
    label = models.CharField(
        max_length=200,
        help_text="Human-readable label for UI, e.g. 'Create Ticket'",
    )
    category = models.ForeignKey(
        PermissionCategory,
        on_delete=models.PROTECT,      # don't allow deleting category with children
        related_name="permissions",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category__permission_category_name", "label"]

    def __str__(self):
        return f"{self.label} ({self.code})"

    def clean(self):
        # keep codes safe & consistent
        if not all(c.isalnum() or c in "._-" for c in self.code):
            raise ValidationError({
                "code": "Code must only contain letters, numbers, dots, underscores, or hyphens."
            })


class Role(models.Model):
    """Role bundles permissions together (Admin, Developer, Support, etc.)."""
    role_name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)

    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
    )

    is_active = models.BooleanField(default=True, db_index=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="roles_created",
    )
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="roles_modified",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower('role_name'),
                name='unique_role_role_name_case_insensitive'
            )
        ]
        # ordering = ["role_name"]

    def __str__(self):
        return self.role_name






class RBACUserMixin(models.Model):
    """
    Abstract mixin to add RBAC to your custom User model.
    Optimized with distributed caching (Redis).
    """
    roles = models.ManyToManyField(
        Role,
        blank=True,
        related_name="users",
    )

    class Meta:
        abstract = True

    def __get_cache_key(self):
        return f"user_permissions:{self.id}"

    def get_all_permissions(self):
        """
        Returns cached set of permission codes.
        - Fast: O(1) lookup
        - Safe: invalidated on role/perm changes
        - Handles superuser
        """
        cache_key = self.__get_cache_key()

        cached = cache.get(cache_key)
        if cached is not None:
            # ALWAYS normalize in-memory
            return set(c.strip().lower() for c in cached)

        # --- DB Lookup ---
        if getattr(self, "is_superuser", False):
            perms = Permission.objects.filter(is_active=True).values_list("code", flat=True)
        else:
            roles = (
                self.roles.filter(is_active=True)
                .prefetch_related(
                    Prefetch(
                        "permissions",
                        queryset=Permission.objects.filter(is_active=True),
                    )
                )
            )
            codes = set()
            for role in roles:
                for perm in role.permissions.all():
                    codes.add(perm.code)

            perms = codes

        # Normalize
        normalized = set(c.strip().lower() for c in perms)

        # Cache 6 hours (enterprise safe)
        cache.set(cache_key, list(normalized), timeout=6 * 3600)

        return normalized

    def has_role_permission(self, perm_code: str) -> bool:
        """
        Constant-time membership test.
        """
        if not getattr(self, "is_active", True):
            return False

        if getattr(self, "is_superuser", False):
            return True

        perm_code = perm_code.strip().lower()

        return perm_code in self.get_all_permissions()

    def clear_permission_cache(self):
        """
        Invalidate cache manually (admin/use case/method override)
        """
        cache.delete(self.__get_cache_key())
