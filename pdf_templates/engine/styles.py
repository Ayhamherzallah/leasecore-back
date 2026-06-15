"""Visual style specs for the document template library.

Each template shares one polished, direction-aware layout engine but differs
through a StyleSpec: header treatment, table header, totals, fonts, accents.
"""

from dataclasses import dataclass, field

from .fonts import FONT_REGULAR, FONT_BOLD, FONT_MEDIUM, FONT_SERIF

TEMPLATE_MODERN = 'modern'
TEMPLATE_MINIMAL = 'minimal'
TEMPLATE_CORPORATE = 'corporate'
TEMPLATE_CLASSIC = 'classic'
TEMPLATE_VIVID = 'vivid'
TEMPLATE_ELEGANT = 'elegant'


@dataclass
class StyleSpec:
    id: str
    # header: 'panel' | 'band' | 'sidebar' | 'minimal' | 'bordered' | 'centered'
    header: str
    # table_header: 'solid' | 'underline' | 'soft'
    table_header: str
    # totals: 'card' | 'filled' | 'plain' | 'bordered'
    totals: str
    # cards: 'filled' | 'bordered' | 'plain'
    cards: str
    body_font: str = FONT_REGULAR
    bold_font: str = FONT_BOLD
    medium_font: str = FONT_MEDIUM
    title_size: int = 22
    uppercase_labels: bool = True
    accent_rule: bool = True
    footer: str = 'line'  # 'line' | 'band' | 'minimal'


STYLES = {
    TEMPLATE_MODERN: StyleSpec(
        id=TEMPLATE_MODERN, header='panel', table_header='solid',
        totals='card', cards='filled', footer='line',
    ),
    TEMPLATE_MINIMAL: StyleSpec(
        id=TEMPLATE_MINIMAL, header='minimal', table_header='underline',
        totals='plain', cards='plain', accent_rule=False, footer='minimal',
        title_size=24,
    ),
    TEMPLATE_CORPORATE: StyleSpec(
        id=TEMPLATE_CORPORATE, header='band', table_header='soft',
        totals='card', cards='bordered', footer='band',
    ),
    TEMPLATE_CLASSIC: StyleSpec(
        id=TEMPLATE_CLASSIC, header='bordered', table_header='underline',
        totals='bordered', cards='bordered', footer='line',
        body_font=FONT_SERIF, bold_font=FONT_SERIF, medium_font=FONT_SERIF,
        uppercase_labels=False, title_size=24,
    ),
    TEMPLATE_VIVID: StyleSpec(
        id=TEMPLATE_VIVID, header='sidebar', table_header='solid',
        totals='filled', cards='filled', footer='line',
        title_size=26,
    ),
    TEMPLATE_ELEGANT: StyleSpec(
        id=TEMPLATE_ELEGANT, header='centered', table_header='underline',
        totals='plain', cards='plain', accent_rule=True, footer='minimal',
        body_font=FONT_SERIF, bold_font=FONT_SERIF, medium_font=FONT_SERIF,
        uppercase_labels=False, title_size=26,
    ),
}


def get_style(template_id):
    return STYLES.get(template_id, STYLES[TEMPLATE_MODERN])


# Frontend-facing metadata (names, descriptions, preview hint).
PDF_TEMPLATE_CHOICES = [
    (TEMPLATE_MODERN, 'Executive'),
    (TEMPLATE_MINIMAL, 'Minimal'),
    (TEMPLATE_CORPORATE, 'Corporate'),
    (TEMPLATE_CLASSIC, 'Classic'),
    (TEMPLATE_VIVID, 'Vivid'),
    (TEMPLATE_ELEGANT, 'Elegant'),
]

PDF_TEMPLATES = [
    {
        'id': TEMPLATE_MODERN,
        'name_en': 'Executive',
        'name_ar': 'تنفيذي',
        'description_en': 'Clean letterhead with logo, a reference panel, and crisp summary cards.',
        'description_ar': 'ترويسة أنيقة مع الشعار، لوحة مرجعية، وبطاقات ملخص واضحة.',
        'layout': 'panel',
    },
    {
        'id': TEMPLATE_MINIMAL,
        'name_en': 'Minimal',
        'name_ar': 'بسيط',
        'description_en': 'Spacious, typography-led layout with hairline rules and no heavy fills.',
        'description_ar': 'تصميم فسيح يعتمد على الطباعة مع خطوط رفيعة وبدون تعبئة ثقيلة.',
        'layout': 'minimal',
    },
    {
        'id': TEMPLATE_CORPORATE,
        'name_en': 'Corporate',
        'name_ar': 'مؤسسي',
        'description_en': 'Full-width header and footer bands for a bold, branded business feel.',
        'description_ar': 'شريط رأس وتذييل بعرض كامل لإحساس مؤسسي قوي بالعلامة.',
        'layout': 'band',
    },
    {
        'id': TEMPLATE_CLASSIC,
        'name_en': 'Classic',
        'name_ar': 'كلاسيكي',
        'description_en': 'Formal serif typeface inside a framed border — a traditional voucher look.',
        'description_ar': 'خط رسمي بحواف مؤطرة — مظهر سند تقليدي.',
        'layout': 'bordered',
    },
    {
        'id': TEMPLATE_VIVID,
        'name_en': 'Vivid',
        'name_ar': 'حيوي',
        'description_en': 'A bold colored header block with white title for a confident, modern look.',
        'description_ar': 'كتلة رأس ملوّنة جريئة بعنوان أبيض لمظهر عصري واثق.',
        'layout': 'sidebar',
    },
    {
        'id': TEMPLATE_ELEGANT,
        'name_en': 'Elegant',
        'name_ar': 'أنيق',
        'description_en': 'Centered serif heading with refined accent rules and generous spacing.',
        'description_ar': 'عنوان متوسط بخط أنيق مع خطوط تمييز رفيعة ومسافات مريحة.',
        'layout': 'centered',
    },
]
