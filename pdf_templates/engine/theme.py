from dataclasses import dataclass
from typing import Optional

from reportlab.lib.colors import HexColor, white, black

from ..template_registry import TEMPLATE_MODERN, TEMPLATE_CLASSIC, TEMPLATE_MINIMAL, TEMPLATE_CORPORATE
from .fonts import FONT_REGULAR, FONT_BOLD


@dataclass
class PdfTheme:
    template: str
    primary: HexColor
    secondary: HexColor
    accent: HexColor
    dark: HexColor
    gray: HexColor
    light_bg: HexColor
    success: HexColor
    danger: HexColor
    company_name_en: str
    company_name_ar: str
    company_address_en: str
    company_address_ar: str
    footer_text: str
    logo_path: Optional[str]
    logo_reader: Optional[object] = None  # reportlab ImageReader when using remote storage
    font_name: str = FONT_REGULAR
    font_bold: str = FONT_BOLD

    @classmethod
    def from_profile(cls, profile, font_name=FONT_REGULAR):
        from .media_utils import resolve_storage_file_path, open_image_reader

        logo_path = None
        logo_reader = None
        if profile.logo:
            logo_path = resolve_storage_file_path(profile.logo)
            if not logo_path:
                logo_reader = open_image_reader(profile.logo)

        return cls(
            template=profile.template,
            primary=HexColor(profile.primary_color),
            secondary=HexColor(profile.secondary_color),
            accent=HexColor(profile.accent_color),
            dark=HexColor(profile.secondary_color),
            gray=HexColor('#64748b'),
            light_bg=HexColor('#f8fafc'),
            success=HexColor('#10b981'),
            danger=HexColor('#ef4444'),
            company_name_en=profile.company_name_en or profile.building.name,
            company_name_ar=profile.company_name_ar or profile.building.name,
            company_address_en=profile.company_address_en or profile.building.address or '',
            company_address_ar=profile.company_address_ar or profile.building.address or '',
            footer_text=profile.footer_text or '',
            logo_path=logo_path,
            logo_reader=logo_reader,
            font_name=font_name,
            font_bold=FONT_BOLD if font_name == FONT_REGULAR else font_name,
        )

    @classmethod
    def default_for_building(cls, building, font_name=FONT_REGULAR):
        """Fallback when no branding profile exists yet."""
        return cls(
            template=TEMPLATE_MODERN,
            primary=HexColor('#5bb5a2'),
            secondary=HexColor('#1e2d3d'),
            accent=HexColor('#4a9e8d'),
            dark=HexColor('#1e2d3d'),
            gray=HexColor('#64748b'),
            light_bg=HexColor('#f8fafc'),
            success=HexColor('#10b981'),
            danger=HexColor('#ef4444'),
            company_name_en=building.name if building else 'Abu Rakhia Plaza',
            company_name_ar=building.name if building else 'مجمع أبو رخية',
            company_address_en=building.address if building else '',
            company_address_ar=building.address if building else '',
            footer_text='',
            logo_path=None,
            font_name=font_name,
            font_bold=FONT_BOLD,
        )

    @classmethod
    def preset(cls, template_id, building=None, font_name=FONT_REGULAR):
        """Layout-only preset — colors stay at sensible defaults, user branding overrides."""
        return cls(
            template=template_id,
            primary=HexColor('#5bb5a2'),
            secondary=HexColor('#1e2d3d'),
            accent=HexColor('#4a9e8d'),
            dark=HexColor('#1e2d3d'),
            gray=HexColor('#64748b'),
            light_bg=HexColor('#f8fafc'),
            success=HexColor('#10b981'),
            danger=HexColor('#ef4444'),
            company_name_en=building.name if building else 'Abu Rakhia Plaza',
            company_name_ar=building.name if building else 'مجمع أبو رخية',
            company_address_en=building.address if building else '',
            company_address_ar=building.address if building else '',
            footer_text='',
            logo_path=None,
            font_name=font_name,
            font_bold=FONT_BOLD,
        )
