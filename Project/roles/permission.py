

from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

class HasPermissionCode(BasePermission):
    """
    Advanced RBAC Permission Class
    Supports:
    ✔ permission_code = "roles.view"
    ✔ permission_codes = ["roles.view", "roles.read"]
    ✔ permission_map = { "POST": "roles.create", "GET": "roles.view" }

    Usage:
        class RoleView(APIView):
            permission_classes = [IsAuthenticated, HasPermissionCode]
            permission_code = "roles.view"
    """

    def _normalize_code(self, code: str):
        return code.strip().lower()

    def has_permission(self, request, view):
        user = request.user

        # 1️⃣ Must be authenticated
        if not user or not user.is_authenticated or not getattr(user, "is_active", False):
            raise PermissionDenied("Authentication required.")

        # 2️⃣ Superuser = bypass
        if getattr(user, "is_superuser", False):
            return True

        # 3️⃣ Determine permission code
        code = getattr(view, "permission_code", None)
        codes = getattr(view, "permission_codes", None)
        method_map = getattr(view, "permission_map", None)

        # --- priority ---
        # permission_map > permission_code > permission_codes

        # 3A — Method specific permission
        if method_map:
            method_code = method_map.get(request.method)
            if method_code:
                code = method_code

        # 3B — Single permission
        if code:
            code = self._normalize_code(code)

            if user.has_role_permission(code):
                return True

            logger.warning(f"[RBAC] DENIED User:{user.id} Missing:{code}")
            raise PermissionDenied(f"You do not have required permission: {code}")

        # 3C — Multiple permissions (any allowed)
        if codes:
            normalized = set(self._normalize_code(c) for c in codes)

            for perm in normalized:
                if user.has_role_permission(perm):
                    return True

            logger.warning(f"[RBAC] DENIED User:{user.id} Missing any of:{normalized}")
            raise PermissionDenied(f"Missing one of required permissions: {list(normalized)}")

        # 4️⃣ If developer forgot to add permission code
        raise PermissionDenied("RBAC permission_code not configured for this endpoint.")
