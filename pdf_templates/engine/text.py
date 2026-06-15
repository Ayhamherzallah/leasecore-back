import re

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import ShapedStr, shapeStr

# Arabic + presentation forms
_ARABIC_RE = re.compile(
    r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
)
_LATIN_RE = re.compile(r'[A-Za-z]')


def has_arabic(text):
    if not text:
        return False
    return bool(_ARABIC_RE.search(str(text)))


def has_latin(text):
    if not text:
        return False
    return bool(_LATIN_RE.search(str(text)))


def split_bilingual(label, sep=' / '):
    if not label:
        return '', ''
    text = str(label).strip()
    if sep in text:
        left, right = text.split(sep, 1)
        left, right = left.strip(), right.strip()
        if has_arabic(left):
            return right, left
        return left, right
    if has_arabic(text):
        return '', text
    return text, ''


def _font_shapable(font_name):
    if font_name == 'Helvetica':
        return False
    try:
        font = pdfmetrics.getFont(font_name)
    except KeyError:
        return False
    return bool(getattr(font, 'shapable', False))


def _is_arabic_char(ch):
    return bool(_ARABIC_RE.match(ch))


def _split_runs(text):
    """Split into runs of (text, is_arabic). Strong chars: Arabic letters (RTL)
    vs Latin letters/digits (LTR). Neutrals (spaces, punctuation like the dot in
    'د.أ') attach to the current run so they don't fragment it."""
    runs = []
    buf = ''
    buf_ar = None
    for ch in text:
        if _is_arabic_char(ch):
            is_ar = True
        elif ch.isalnum():
            is_ar = False
        else:  # neutral: space / punctuation
            is_ar = buf_ar if buf_ar is not None else False
        if buf_ar is None:
            buf, buf_ar = ch, is_ar
        elif is_ar == buf_ar:
            buf += ch
        else:
            runs.append((buf, buf_ar))
            buf, buf_ar = ch, is_ar
    if buf:
        runs.append((buf, buf_ar))
    return runs


def shape_text(text, font_name, font_size):
    """Shape a PURE-Arabic string. Mixed strings should use prepare_visual."""
    if text is None:
        return ''
    text_str = str(text)
    if not text_str or not _font_shapable(font_name) or not has_arabic(text_str):
        return text_str
    if has_latin(text_str) or any(c.isdigit() for c in text_str):
        return text_str
    try:
        return shapeStr(text_str, font_name, font_size)
    except Exception:
        return text_str


def prepare_visual(text, font_name, font_size, base_rtl):
    """
    Return (runs, total_width) where runs is a list of (prepared, width) in
    visual left-to-right order. Arabic runs are HarfBuzz-shaped; digit/Latin
    runs are kept LTR. Solves the Arabic + numbers bidi problem.
    """
    if text is None:
        text = ''
    text = str(text)
    raw_runs = _split_runs(text)
    shapable = _font_shapable(font_name)
    space_w = pdfmetrics.stringWidth(' ', font_name, font_size)

    runs = []
    for run_text, is_ar in raw_runs:
        stripped = run_text.strip()
        if not stripped:
            continue
        if is_ar and shapable:
            try:
                prepared = shapeStr(stripped, font_name, font_size)
            except Exception:
                prepared = stripped
        else:
            prepared = stripped
        runs.append((prepared, text_width(prepared, font_name, font_size)))

    if base_rtl:
        runs = list(reversed(runs))

    # Re-insert single spaces between adjacent runs.
    out = []
    total = 0
    for i, (prepared, w) in enumerate(runs):
        if i > 0:
            out.append((' ', space_w))
            total += space_w
        out.append((prepared, w))
        total += w
    return out, total


def text_width(text, font_name, font_size):
    if isinstance(text, ShapedStr) and hasattr(text, '__shapeData__'):
        return sum(g.x_advance for g in text.__shapeData__) * font_size / 1000
    return pdfmetrics.stringWidth(str(text), font_name, font_size)
