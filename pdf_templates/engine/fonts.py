import os

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_REGULAR = 'Tajawal'
FONT_MEDIUM = 'Tajawal-Medium'
FONT_BOLD = 'Tajawal-Bold'

# Serif family (used by classic / elegant templates). Amiri ships regular only,
# so bold falls back to the regular face at a larger size.
FONT_SERIF = 'Amiri'
FONT_SERIF_BOLD = 'Amiri'

_registered = False


def _font_dirs():
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return [
        os.path.join(settings.BASE_DIR, 'assets', 'fonts'),
        os.path.join(backend_dir, 'assets', 'fonts'),
        os.path.join(os.getcwd(), 'assets', 'fonts'),
    ]


def _find_font(filename):
    for directory in _font_dirs():
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    return None


def register_pdf_fonts():
    """Register Tajawal (sans) + Amiri (serif) with HarfBuzz shaping."""
    global _registered
    if _registered and FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return FONT_REGULAR

    mapping = [
        (FONT_REGULAR, 'Tajawal-Regular.ttf'),
        (FONT_MEDIUM, 'Tajawal-Medium.ttf'),
        (FONT_BOLD, 'Tajawal-Bold.ttf'),
        (FONT_SERIF, 'Amiri-Regular.ttf'),
    ]

    loaded = False
    for font_name, filename in mapping:
        if font_name in pdfmetrics.getRegisteredFontNames():
            loaded = True
            continue
        path = _find_font(filename)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(font_name, path, shapable=True))
                loaded = True
            except Exception:
                continue

    if loaded:
        pdfmetrics.registerFontFamily(
            FONT_REGULAR,
            normal=FONT_REGULAR,
            bold=FONT_BOLD,
            italic=FONT_REGULAR,
            boldItalic=FONT_BOLD,
        )
        if FONT_SERIF in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFontFamily(
                FONT_SERIF,
                normal=FONT_SERIF,
                bold=FONT_SERIF,
                italic=FONT_SERIF,
                boldItalic=FONT_SERIF,
            )

    _registered = True
    return FONT_REGULAR if loaded else 'Helvetica'


def has_serif():
    return FONT_SERIF in pdfmetrics.getRegisteredFontNames()
