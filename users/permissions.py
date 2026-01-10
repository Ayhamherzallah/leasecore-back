from rest_framework import permissions
from .models import Role

# Role-based Checks
class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'profile') and 
            request.user.profile.role == Role.SUPER_ADMIN
        )

class IsAccountant(permissions.BasePermission):
    """
    Allows access to Accountants and Super Admins.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'profile') and 
            request.user.profile.role in [Role.SUPER_ADMIN, Role.ACCOUNTANT]
        )

class IsManager(permissions.BasePermission):
    """
    Allows access to Managers, Accountants, and Super Admins.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            hasattr(request.user, 'profile') and 
            request.user.profile.role in [Role.SUPER_ADMIN, Role.ACCOUNTANT, Role.MANAGER]
        )

# Command-based Permissions
class CanPerformFinancialCommand(permissions.BasePermission):
    """
    Checks if user can perform financial commands (Issue, Payment, Cheque Ops).
    Allowed: SUPER_ADMIN, ACCOUNTANT.
    Denies write actions for MANAGER.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # SAFE_METHODS (GET, HEAD, OPTIONS) are allowed for any authenticated user (Manager included)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write methods require Accountant/Admin role
        if hasattr(request.user, 'profile'):
            return request.user.profile.role in [Role.SUPER_ADMIN, Role.ACCOUNTANT]
            
        return False
