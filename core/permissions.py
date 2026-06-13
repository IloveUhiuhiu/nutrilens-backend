from rest_framework.permissions import BasePermission


def require_perm(*perms):
    """
    Returns a DRF BasePermission subclass that requires the caller to hold every listed
    Django permission.  Superusers bypass the check.  Unauthenticated callers always fail.

    Usage:
        @permission_classes([require_perm("analysis.add_mealentry")])
        def meal_from_inference(request): ...
    """
    class _Permission(BasePermission):
        required_perms = perms
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if request.user.is_superuser:
                return True
            return all(request.user.has_perm(p) for p in self.required_perms)

    _Permission.__name__ = "RequirePerm_" + "_".join(p.replace(".", "_") for p in perms)
    _Permission.__qualname__ = _Permission.__name__
    return _Permission


def method_perm(**kwargs):
    """
    Returns a DRF BasePermission subclass where the required Django permission depends on
    the HTTP method.  Superusers bypass all checks.  Methods not listed in kwargs are denied.

    Each value may be a single permission string or a list/tuple of strings (all required).

    Usage:
        @permission_classes([method_perm(
            GET="accounts.view_activitylevel",
            POST="accounts.add_activitylevel",
            PATCH="accounts.change_activitylevel",
            DELETE="accounts.delete_activitylevel",
        )])
        def admin_activity_level_list_create(request): ...
    """
    class _Permission(BasePermission):
        method_perms = kwargs
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view):
            if not (request.user and request.user.is_authenticated):
                return False
            if request.user.is_superuser:
                return True
            perm = self.method_perms.get(request.method)
            if perm is None:
                return False
            if isinstance(perm, (list, tuple)):
                return all(request.user.has_perm(p) for p in perm)
            return request.user.has_perm(perm)

    _Permission.__name__ = "MethodPerm_" + "_".join(kwargs.keys())
    _Permission.__qualname__ = _Permission.__name__
    return _Permission
