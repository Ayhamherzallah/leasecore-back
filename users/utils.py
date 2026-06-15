from properties.models import Building
from .models import Role, UserProfile


def ensure_user_profile(user):
    """Ensure every auth user has a profile; sync Django superusers to platform admin role."""
    if not user or not user.is_authenticated:
        return None

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': Role.SUPER_ADMIN if user.is_superuser else Role.BUILDING_MANAGER},
    )

    if user.is_superuser and profile.role != Role.SUPER_ADMIN:
        profile.role = Role.SUPER_ADMIN
        profile.save(update_fields=['role'])

    return profile


def is_platform_admin(user):
    """LeaseCore platform staff — not vendor users."""
    if not user or not user.is_authenticated:
        return False
    ensure_user_profile(user)
    return hasattr(user, 'profile') and user.profile.role == Role.SUPER_ADMIN


def get_user_role(user):
    if not user or not user.is_authenticated:
        return Role.BUILDING_MANAGER
    ensure_user_profile(user)
    return user.profile.role


def is_building_manager(user):
    if not user or not user.is_authenticated:
        return False
    ensure_user_profile(user)
    return hasattr(user, 'profile') and user.profile.role == Role.BUILDING_MANAGER


def can_write_operations(user):
    """Full read/write within assigned buildings (property, tenants, contracts, billing)."""
    if not user or not user.is_authenticated:
        return False
    if is_platform_admin(user):
        return True
    ensure_user_profile(user)
    return hasattr(user, 'profile') and user.profile.role in (
        Role.BUILDING_MANAGER,
        Role.ACCOUNTANT,
    )


def get_accessible_buildings(user):
    """Platform admins see all buildings; vendor users see only assigned ones."""
    if not user or not user.is_authenticated:
        return Building.objects.none()
    if is_platform_admin(user):
        return Building.objects.all()
    if hasattr(user, 'profile'):
        return user.profile.buildings.all()
    return Building.objects.none()
