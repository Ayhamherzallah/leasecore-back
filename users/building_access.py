from django.db.models import Q

from .utils import get_accessible_buildings, is_platform_admin


def get_accessible_building_ids(user):
    return list(get_accessible_buildings(user).values_list('pk', flat=True))


def user_can_access_building(user, building_id):
    if is_platform_admin(user):
        return True
    if building_id is None:
        return False
    return int(building_id) in get_accessible_building_ids(user)


def scope_by_building_ids(queryset, user, lookup):
    """Filter queryset where `lookup` resolves to a building id (e.g. 'floor__building_id')."""
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(**{f'{lookup}__in': ids})


def scope_floors(queryset, user):
    return scope_by_building_ids(queryset, user, 'building_id')


def scope_units(queryset, user):
    return scope_by_building_ids(queryset, user, 'floor__building_id')


def scope_contracts(queryset, user):
    return scope_by_building_ids(queryset, user, 'unit__floor__building_id')


def scope_tenants(queryset, user):
    """
    Tenants are visible only when they belong to an accessible building —
    either as their owner building or via a contract in an accessible building.
    Tenants with no building owner are NOT shown to vendors (admin only).
    """
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(
        Q(building_id__in=ids)
        | Q(contracts__unit__floor__building_id__in=ids)
    ).distinct()


def scope_invoices(queryset, user):
    """
    Invoices are scoped by their owner building (authoritative) with a contract
    fallback for safety. Invoices with no building/contract are admin-only.
    """
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(
        Q(building_id__in=ids)
        | Q(contract__unit__floor__building_id__in=ids)
    ).distinct()


def scope_payments(queryset, user):
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(
        Q(invoice__building_id__in=ids)
        | Q(invoice__contract__unit__floor__building_id__in=ids)
    ).distinct()


def scope_cheques(queryset, user):
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(
        Q(payment__invoice__building_id__in=ids)
        | Q(payment__invoice__contract__unit__floor__building_id__in=ids)
    ).distinct()


def scope_expenses(queryset, user):
    return scope_by_building_ids(queryset, user, 'building_id')


def scope_ledger(queryset, user):
    return scope_by_building_ids(queryset, user, 'building_id')


def scope_catalog(queryset, user):
    """
    Catalogs (invoice types, expense categories): a vendor sees their own
    building-scoped entries plus shared system defaults (building IS NULL).
    """
    if is_platform_admin(user):
        return queryset
    ids = get_accessible_building_ids(user)
    if not ids:
        return queryset.filter(building__isnull=True)
    return queryset.filter(Q(building_id__in=ids) | Q(building__isnull=True))


def scope_fixed_costs(queryset, user):
    return scope_by_building_ids(queryset, user, 'building_id')


def scope_fixed_cost_occurrences(queryset, user):
    return scope_by_building_ids(queryset, user, 'fixed_cost__building_id')
