from rest_framework import permissions
from .models import Role
from .utils import is_platform_admin, ensure_user_profile, can_write_operations


class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return is_platform_admin(request.user)


class IsAccountant(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if is_platform_admin(request.user):
            return True
        ensure_user_profile(request.user)
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (Role.ACCOUNTANT, Role.BUILDING_MANAGER)
        )


class IsManager(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if is_platform_admin(request.user):
            return True
        ensure_user_profile(request.user)
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role in (
                Role.ACCOUNTANT,
                Role.BUILDING_MANAGER,
                Role.MANAGER,
            )
        )


class CanPerformFinancialCommand(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if is_platform_admin(request.user):
            return True

        ensure_user_profile(request.user)
        if hasattr(request.user, 'profile'):
            return request.user.profile.role in (Role.ACCOUNTANT, Role.BUILDING_MANAGER)

        return False


class CanManageBuildingOperations(permissions.BasePermission):
    """Authenticated read; writes for platform admins and building managers."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        if is_platform_admin(request.user):
            return True

        ensure_user_profile(request.user)
        return (
            hasattr(request.user, 'profile')
            and request.user.profile.role == Role.BUILDING_MANAGER
        )


class CanRecordExpenses(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return can_write_operations(request.user)
