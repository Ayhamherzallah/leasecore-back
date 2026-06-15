import os

from django.conf import settings

from properties.models import Building
from ..models import PdfBrandingProfile
from .fonts import register_pdf_fonts
from .theme import PdfTheme


def _default_logo_path():
    path = os.path.join(settings.MEDIA_ROOT, 'AbuRakhiaLogo.png')
    return path if os.path.exists(path) else None


def get_branding_profile(building_id):
    if not building_id:
        return None
    try:
        return PdfBrandingProfile.objects.select_related('building').get(building_id=building_id)
    except PdfBrandingProfile.DoesNotExist:
        return None


def get_or_create_branding_profile(building_id):
    if not building_id:
        return None
    building = Building.objects.filter(pk=building_id).first()
    if not building:
        return None
    profile, _ = PdfBrandingProfile.objects.get_or_create(building=building)
    return profile


def resolve_theme(building_id=None):
    font_name = register_pdf_fonts()
    profile = get_branding_profile(building_id)
    if profile:
        theme = PdfTheme.from_profile(profile, font_name)
        if not theme.logo_path and not theme.logo_reader:
            theme.logo_path = _default_logo_path()
        return theme

    building = Building.objects.filter(pk=building_id).first() if building_id else None
    theme = PdfTheme.default_for_building(building, font_name)
    theme.logo_path = _default_logo_path()
    return theme


def _only_branding_building_id():
    """If exactly one branding profile exists, use it as a sensible fallback."""
    qs = PdfBrandingProfile.objects.all()
    if qs.count() == 1:
        return qs.first().building_id
    return None


def _building_id_for_invoice(invoice):
    if invoice.contract and invoice.contract.unit and invoice.contract.unit.floor:
        return invoice.contract.unit.floor.building_id
    # Contract-less invoice (e.g. parking): fall back to the tenant's contracts.
    if invoice.tenant_id:
        contract = (
            invoice.tenant.contracts.select_related('unit__floor')
            .filter(unit__floor__building__isnull=False)
            .first()
        )
        if contract and contract.unit and contract.unit.floor:
            return contract.unit.floor.building_id
    return _only_branding_building_id()


def theme_from_invoice(invoice):
    return resolve_theme(_building_id_for_invoice(invoice))


def theme_from_payment(payment):
    if payment.invoice:
        return resolve_theme(_building_id_for_invoice(payment.invoice))
    return resolve_theme(None)


def theme_from_expense(expense):
    building_id = expense.building_id if expense.building_id else None
    return resolve_theme(building_id)
