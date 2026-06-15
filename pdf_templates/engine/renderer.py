"""Direction-aware, monolingual PDF layout engine.

A single polished document layout, parameterized by a StyleSpec (the chosen
template) and a Localizer (the chosen language + reading direction).
"""

from reportlab.lib.colors import HexColor, white, black, Color
from reportlab.pdfbase.ttfonts import ShapedStr

from .fonts import register_pdf_fonts
from .text import has_arabic, prepare_visual
from .styles import get_style


def _mix(c1, c2, t):
    return Color(
        c1.red + (c2.red - c1.red) * t,
        c1.green + (c2.green - c1.green) * t,
        c1.blue + (c2.blue - c1.blue) * t,
    )


def _tint(color, t):
    """Lighten a color toward white by factor t (0..1)."""
    return _mix(color, white, t)


class DocRenderer:
    MARGIN = 50

    def __init__(self, canvas, width, height, theme, loc, style=None):
        register_pdf_fonts()
        self.c = canvas
        self.width = width
        self.height = height
        self.theme = theme
        self.loc = loc
        self.rtl = loc.rtl
        self.style = style or get_style(theme.template)
        self.font = self.style.body_font
        self.font_bold = self.style.bold_font
        self.font_medium = self.style.medium_font

    # ── Geometry (logical: 0 = leading edge, content_w = trailing edge) ────

    @property
    def content_w(self):
        return self.width - 2 * self.MARGIN

    def from_lead(self, d):
        return (self.MARGIN + d) if not self.rtl else (self.width - self.MARGIN - d)

    def from_trail(self, d):
        return (self.width - self.MARGIN - d) if not self.rtl else (self.MARGIN + d)

    @property
    def lead_x(self):
        return self.from_lead(0)

    @property
    def trail_x(self):
        return self.from_trail(0)

    # ── Text primitives ────────────────────────────────────────────────────

    def _prepared(self, s, font, size):
        runs, total = prepare_visual(s, font, size, self.rtl)
        return runs, total

    def _put_run(self, x, y, prepared, font, size):
        self.c.setFont(font, size)
        if isinstance(prepared, ShapedStr):
            t = self.c.beginText(x, y)
            t.setFont(font, size)
            t.textLine(prepared)
            self.c.drawText(t)
        else:
            self.c.drawString(x, y, prepared)

    def _put_runs(self, x_left, y, runs, font, size):
        x = x_left
        for prepared, w in runs:
            self._put_run(x, y, prepared, font, size)
            x += w

    def text_at(self, x, y, s, anchor='left', font=None, size=10, color=None):
        font = font or self.font
        if color is not None:
            self.c.setFillColor(color)
        runs, total = self._prepared(s, font, size)
        if anchor == 'left':
            x_left = x
        elif anchor == 'right':
            x_left = x - total
        else:  # center
            x_left = x - total / 2
        self._put_runs(x_left, y, runs, font, size)
        return self

    def draw_start(self, offset, y, s, font=None, size=10, color=None):
        """Text anchored at the leading reading edge (+offset toward trailing)."""
        x = self.from_lead(offset)
        anchor = 'left' if not self.rtl else 'right'
        return self.text_at(x, y, s, anchor, font, size, color)

    def draw_end(self, offset, y, s, font=None, size=10, color=None):
        """Text anchored at the trailing reading edge (+offset toward leading)."""
        x = self.from_trail(offset)
        anchor = 'right' if not self.rtl else 'left'
        return self.text_at(x, y, s, anchor, font, size, color)

    def draw_center(self, y, s, font=None, size=10, color=None, cx=None):
        cx = cx if cx is not None else self.width / 2
        return self.text_at(cx, y, s, 'center', font, size, color)

    def label(self, s):
        return s.upper() if (self.style.uppercase_labels and not has_arabic(s)) else s

    def _measure(self, s, font, size):
        _, total = prepare_visual(s, font, size, self.rtl)
        return total

    def _truncate(self, s, font, size, max_w):
        s = '' if s is None else str(s)
        if self._measure(s, font, size) <= max_w:
            return s
        ell = '…'
        while s and self._measure(s + ell, font, size) > max_w:
            s = s[:-1]
        return (s + ell) if s else s

    # ── Shapes ──────────────────────────────────────────────────────────────

    def rule(self, y, color=None, lw=0.75, x0=None, x1=None):
        c = self.c
        c.setStrokeColor(color or HexColor('#e5e8ec'))
        c.setLineWidth(lw)
        c.line(x0 if x0 is not None else self.MARGIN, y,
               x1 if x1 is not None else self.width - self.MARGIN, y)

    def logo(self, x, y, max_w=110, max_h=58, anchor='lead'):
        src = None
        if getattr(self.theme, 'logo_path', None):
            src = self.theme.logo_path
        elif getattr(self.theme, 'logo_reader', None):
            src = self.theme.logo_reader
        if not src:
            return False
        draw_x = x if anchor == 'lead' else (x - max_w)
        try:
            self.c.drawImage(src, draw_x, y, width=max_w, height=max_h,
                             preserveAspectRatio=True, mask='auto', anchor='sw')
            return True
        except Exception:
            return False

    # ── Company / status helpers ─────────────────────────────────────────────

    def company_name(self):
        if self.rtl:
            return (self.theme.company_name_ar or self.theme.company_name_en or '').strip()
        return (self.theme.company_name_en or self.theme.company_name_ar or '').strip()

    def company_address(self):
        if self.rtl:
            return (self.theme.company_address_ar or self.theme.company_address_en or '').strip()
        return (self.theme.company_address_en or self.theme.company_address_ar or '').strip()

    def status_badge(self, x, y, text, color, anchor='end', w=96, h=20):
        c = self.c
        # Direction-aware: a badge anchored at the trailing edge grows toward
        # the leading edge (left in LTR, right in RTL).
        if anchor == 'end':
            bx = (x - w) if not self.rtl else x
        elif anchor == 'start':
            bx = x if not self.rtl else (x - w)
        else:
            bx = x - w / 2
        # keep on page
        bx = max(self.MARGIN, min(bx, self.width - self.MARGIN - w))
        c.setFillColor(color)
        c.roundRect(bx, y, w, h, h / 2, stroke=0, fill=1)
        self.text_at(bx + w / 2, y + h / 2 - 3.2, text, 'center', self.font_bold, 8, white)

    # ── Header dispatch ───────────────────────────────────────────────────────

    def header(self, title, ref, status=None):
        fn = {
            'panel': self._header_panel,
            'band': self._header_band,
            'sidebar': self._header_sidebar,
            'minimal': self._header_minimal,
            'bordered': self._header_bordered,
            'centered': self._header_centered,
        }.get(self.style.header, self._header_panel)
        return fn(title, ref, status)

    def _company_block(self, x_offset, y, on='lead'):
        th = self.theme
        name = self.company_name()
        addr = self.company_address()
        draw = self.draw_start if on == 'lead' else self.draw_end
        draw(x_offset, y, name, self.font_bold, 14, th.secondary)
        yy = y - 15
        if addr:
            draw(x_offset, yy, addr[:90], self.font, 8.5, th.gray)
            yy -= 12
        return yy

    def _header_panel(self, title, ref, status):
        th, h, m = self.theme, self.height, self.MARGIN
        top = h - m
        if self.style.accent_rule:
            self.c.setFillColor(th.primary)
            self.c.rect(m, top - 3, self.content_w, 3, fill=1, stroke=0)

        logo_y = top - 64
        has_logo = self.logo(self.from_lead(0), logo_y, 110, 56,
                             anchor='lead' if not self.rtl else 'trail')
        text_off = 124 if has_logo else 0
        self._company_block(text_off, top - 22, on='lead')

        # Reference panel on trailing side
        box_w, box_h = 210, 74
        if not self.rtl:
            box_x = self.width - m - box_w
        else:
            box_x = m
        box_y = top - box_h
        self.c.setFillColor(HexColor('#f7f9fb'))
        self.c.setStrokeColor(HexColor('#e5e8ec'))
        self.c.setLineWidth(0.75)
        self.c.roundRect(box_x, box_y, box_w, box_h, 5, stroke=1, fill=1)
        self.c.setFillColor(th.primary)
        self.c.rect(box_x, box_y + box_h - 3, box_w, 3, fill=1, stroke=0)
        pad = 14
        self.draw_end(pad, box_y + box_h - 26, title, self.font_bold, 18, th.secondary)
        if ref:
            self.draw_end(pad, box_y + 16, ref, self.font_medium, 10, th.gray)
        if status:
            stext, scolor = status
            self.status_badge(self.from_trail(pad), box_y + box_h - 46, stext, scolor,
                              anchor='end', w=92, h=18)

        rule_y = box_y - 14
        self.rule(rule_y, HexColor('#e5e8ec'))
        return rule_y - 22

    def _header_band(self, title, ref, status):
        th, w, h = self.theme, self.width, self.height
        band_h = 92
        band_y = h - band_h
        self.c.setFillColor(HexColor('#f4f6f9'))
        self.c.rect(0, band_y, w, band_h, fill=1, stroke=0)
        self.c.setFillColor(th.primary)
        self.c.rect(0, band_y - 3, w, 3, fill=1, stroke=0)

        logo_y = band_y + (band_h - 52) / 2
        has_logo = self.logo(self.from_lead(0), logo_y, 104, 52,
                             anchor='lead' if not self.rtl else 'trail')
        text_off = 118 if has_logo else 0
        self._company_block(text_off, band_y + band_h - 30, on='lead')

        self.draw_end(0, band_y + band_h - 38, title, self.font_bold, self.style.title_size, th.secondary)
        if ref:
            self.draw_end(0, band_y + band_h - 60, ref, self.font_medium, 10, th.gray)
        if status:
            stext, scolor = status
            self.status_badge(self.from_trail(0), band_y + 18, stext, scolor, anchor='end')
        return band_y - 24

    def _header_sidebar(self, title, ref, status):
        th, w, h = self.theme, self.width, self.height
        block_h = 118
        block_y = h - block_h
        self.c.setFillColor(th.secondary)
        self.c.rect(0, block_y, w, block_h, fill=1, stroke=0)
        self.c.setFillColor(th.primary)
        self.c.rect(0, block_y, w, 5, fill=1, stroke=0)

        m = self.MARGIN
        logo_y = block_y + block_h - 64
        has_logo = self.logo(self.from_lead(0), logo_y, 96, 48,
                             anchor='lead' if not self.rtl else 'trail')
        name = self.company_name()
        name_off = 110 if has_logo else 0
        self.draw_start(name_off, block_y + block_h - 34, name, self.font_bold, 15, white)
        addr = self.company_address()
        if addr:
            self.draw_start(name_off, block_y + block_h - 52, addr[:80], self.font, 8.5, HexColor('#cdd5de'))

        self.draw_end(0, block_y + 40, title, self.font_bold, self.style.title_size, white)
        if ref:
            self.draw_end(0, block_y + 20, ref, self.font_medium, 10, HexColor('#cdd5de'))
        if status:
            stext, scolor = status
            self.status_badge(self.from_trail(0), block_y + block_h - 40, stext, scolor, anchor='end')
        return block_y - 26

    def _header_minimal(self, title, ref, status):
        th, h, m = self.theme, self.height, self.MARGIN
        top = h - m
        has_logo = self.logo(self.from_lead(0), top - 44, 92, 44,
                             anchor='lead' if not self.rtl else 'trail')
        name = self.company_name()
        self.draw_start(0, top - 60 if has_logo else top - 12, name, self.font_bold, 12, th.secondary)

        self.draw_end(0, top - 14, title, self.font_bold, self.style.title_size, th.secondary)
        if ref:
            self.draw_end(0, top - 34, ref, self.font, 10, th.gray)
        if status:
            stext, scolor = status
            self.status_badge(self.from_trail(0), top - 56, stext, scolor, anchor='end')

        rule_y = top - 72
        self.rule(rule_y, HexColor('#d7dce2'), 0.75)
        return rule_y - 24

    def _header_bordered(self, title, ref, status):
        th, w, h, m = self.theme, self.width, self.height, self.MARGIN
        self._draw_frame()
        top = h - m - 16
        has_logo = self.logo(self.width / 2 - 46, top - 50, 92, 46, anchor='lead')
        cy = top - 64 if has_logo else top - 6
        self.draw_center(cy, self.company_name(), self.font_bold, 16, th.secondary)
        addr = self.company_address()
        if addr:
            cy -= 16
            self.draw_center(cy, addr[:90], self.font, 9, th.gray)
        cy -= 26
        self.c.setStrokeColor(th.primary)
        self.c.setLineWidth(1)
        self.c.line(m + 30, cy + 16, w - m - 30, cy + 16)
        self.draw_center(cy, title, self.font_bold, self.style.title_size, th.secondary)
        cy -= 18
        if ref:
            self.draw_center(cy, ref, self.font, 10, th.gray)
            cy -= 14
        if status:
            stext, scolor = status
            self.status_badge(w / 2 + 46, cy + 4, stext, scolor, anchor='end')
        return cy - 16

    def _header_centered(self, title, ref, status):
        th, w, h, m = self.theme, self.width, self.height, self.MARGIN
        top = h - m
        has_logo = self.logo(self.width / 2 - 44, top - 48, 88, 44, anchor='lead')
        cy = top - 64 if has_logo else top - 10
        self.draw_center(cy, self.company_name(), self.font_bold, 15, th.secondary)
        addr = self.company_address()
        if addr:
            cy -= 15
            self.draw_center(cy, addr[:90], self.font, 8.5, th.gray)
        cy -= 30
        # accent rules flanking the title
        tw = self._measure(title, self.font_bold, self.style.title_size)
        gap = tw / 2 + 18
        self.c.setStrokeColor(th.primary)
        self.c.setLineWidth(1)
        self.c.line(m + 20, cy + 6, w / 2 - gap, cy + 6)
        self.c.line(w / 2 + gap, cy + 6, w - m - 20, cy + 6)
        self.draw_center(cy, title, self.font_bold, self.style.title_size, th.secondary)
        cy -= 20
        if ref:
            self.draw_center(cy, ref, self.font, 10, th.gray)
            cy -= 14
        if status:
            stext, scolor = status
            self.draw_center(cy - 2, stext, self.font_bold, 9, scolor)
            cy -= 16
        return cy - 14

    def _draw_frame(self):
        c, w, h, m = self.c, self.width, self.height, self.MARGIN
        c.setStrokeColor(self.theme.secondary)
        c.setLineWidth(1.25)
        c.rect(m - 14, m - 14, w - 2 * (m - 14), h - 2 * (m - 14), stroke=1, fill=0)
        c.setStrokeColor(self.theme.primary)
        c.setLineWidth(0.5)
        c.rect(m - 10, m - 10, w - 2 * (m - 10), h - 2 * (m - 10), stroke=1, fill=0)

    # ── Info area: party card + meta rows ─────────────────────────────────────

    def info_block(self, y, party, meta, status_in_card=None):
        gap = 16
        card_w = (self.content_w - gap) / 2
        rows = max(len(meta), 2)
        card_h = max(96, 50 + rows * 22)
        top = y - card_h
        style = self.style.cards

        # Party card (leading side), details card (trailing side)
        lead_card_x = self.from_lead(0) if not self.rtl else self.from_lead(0) - card_w
        trail_card_x = self.from_trail(card_w) if not self.rtl else self.from_trail(0)
        # Normalize to absolute left coords
        if not self.rtl:
            party_x = self.MARGIN
            details_x = self.MARGIN + card_w + gap
        else:
            party_x = self.width - self.MARGIN - card_w
            details_x = self.MARGIN

        self._card(party_x, top, card_w, card_h, style)
        self._card(details_x, top, card_w, card_h, style)

        # Party content
        if party:
            self._card_title(party_x, card_w, top + card_h - 17, party.get('label', ''))
            self.text_at(self._card_lead(party_x, card_w), top + card_h - 40,
                         party.get('name', ''),
                         'left' if not self.rtl else 'right',
                         self.font_bold, 13, self.theme.dark)
            sub = party.get('sub')
            if sub:
                self.text_at(self._card_lead(party_x, card_w), top + card_h - 57, sub,
                             'left' if not self.rtl else 'right',
                             self.font, 9, self.theme.gray)

        # Details title + rows
        self._card_title(details_x, card_w, top + card_h - 17, self.loc.t('details'))
        ry = top + card_h - 38
        for lbl, val in meta:
            self.text_at(self._card_lead(details_x, card_w), ry, lbl,
                         'left' if not self.rtl else 'right', self.font, 7.5, self.theme.gray)
            self.text_at(self._card_trail(details_x, card_w), ry,
                         self._truncate(val, self.font_medium, 9.5, card_w - 90),
                         'right' if not self.rtl else 'left', self.font_medium, 9.5, self.theme.dark)
            ry -= 22

        if status_in_card:
            stext, scolor = status_in_card
            self.status_badge(self._card_trail(party_x, card_w), top + 14, stext, scolor,
                              anchor='end', w=88, h=18)
        return top - 20

    def _card_lead(self, card_left, card_w):
        return (card_left + 14) if not self.rtl else (card_left + card_w - 14)

    def _card_trail(self, card_left, card_w):
        return (card_left + card_w - 14) if not self.rtl else (card_left + 14)

    def _card_title(self, card_left, card_w, y, text):
        self.text_at(self._card_lead(card_left, card_w), y, self.label(text),
                     'left' if not self.rtl else 'right', self.font_bold, 7.5, self.theme.gray)

    def _card(self, x, y, w, h, style):
        c = self.c
        if style == 'filled':
            c.setFillColor(HexColor('#f7f9fb'))
            c.setStrokeColor(HexColor('#e5e8ec'))
            c.setLineWidth(0.75)
            c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
            c.setFillColor(self.theme.primary)
            c.rect(x, y + h - 2, w, 2, fill=1, stroke=0)
        elif style == 'bordered':
            c.setStrokeColor(HexColor('#d7dce2'))
            c.setLineWidth(0.75)
            c.roundRect(x, y, w, h, 3, stroke=1, fill=0)
        # plain: no chrome

    # ── Items table ───────────────────────────────────────────────────────────

    def items_table(self, y, rows):
        """rows: list of (description, qty_str, unit_price_str, amount_str)."""
        loc = self.loc
        num_w = 70
        qty_w = 56
        # Logical column offsets from leading edge
        desc_a = 0
        desc_b = self.content_w - (qty_w + num_w + num_w)
        qty_b = desc_b + qty_w
        unit_b = qty_b + num_w
        amt_b = unit_b + num_w

        y = self._table_header(y, [
            ('start', desc_a, desc_b, loc.t('description')),
            ('end', desc_b, qty_b, loc.t('qty')),
            ('end', qty_b, unit_b, loc.t('unit_price')),
            ('end', unit_b, amt_b, loc.t('amount')),
        ])

        row_h = 24
        self.c.setFont(self.font, 9.5)
        for idx, (desc, qty, unit, amount) in enumerate(rows):
            if idx % 2 == 1 and self.style.table_header != 'underline':
                self.c.setFillColor(HexColor('#f9fafb'))
                self.c.rect(self.MARGIN, y - 10, self.content_w, row_h, fill=1, stroke=0)
            desc_t = self._truncate(desc, self.font, 9.5, (desc_b - desc_a) - 16)
            self._cell('start', desc_a, desc_b, y, desc_t, self.font, 9.5, self.theme.dark)
            self._cell('end', desc_b, qty_b, y, qty, self.font, 9.5, self.theme.dark)
            self._cell('end', qty_b, unit_b, y, unit, self.font, 9.5, self.theme.dark)
            self._cell('end', unit_b, amt_b, y, amount, self.font_medium, 9.5, self.theme.dark)
            self.rule(y - 12, HexColor('#eef1f4'), 0.5)
            y -= row_h
        return y

    def _table_header(self, y, cols):
        c, th, m = self.c, self.theme, self.MARGIN
        hstyle = self.style.table_header
        header_h = 28
        if hstyle == 'solid':
            c.setFillColor(th.secondary)
            c.roundRect(m, y - 10, self.content_w, header_h, 3, stroke=0, fill=1)
            label_color = white
        elif hstyle == 'soft':
            c.setFillColor(HexColor('#eef1f4'))
            c.rect(m, y - 10, self.content_w, header_h, stroke=0, fill=1)
            c.setFillColor(th.primary)
            c.rect(m, y - 10, self.content_w, 2, fill=1, stroke=0)
            label_color = th.secondary
        else:  # underline
            label_color = th.secondary
        for align, a, b, lbl in cols:
            self._cell(align, a, b, y + 2, self.label(lbl), self.font_bold, 8.5, label_color)
        if hstyle == 'underline':
            self.rule(y - 10, th.secondary, 1)
        return y - header_h - 6

    def _cell(self, align, a, b, y, text, font, size, color):
        pad = 10
        if align == 'start':
            x = self.from_lead(a + pad)
            anchor = 'left' if not self.rtl else 'right'
        else:  # end
            x = self.from_lead(b - pad)
            anchor = 'right' if not self.rtl else 'left'
        self.text_at(x, y, text, anchor, font, size, color)

    # ── Notes ─────────────────────────────────────────────────────────────────

    def notes(self, y, label, text):
        if not text or not str(text).strip():
            return y
        y -= 6
        self.draw_start(0, y, self.label(label), self.font_bold, 8.5, self.theme.gray)
        y -= 14
        for line in str(text).strip().split('\n')[:5]:
            line = line.strip()
            if not line:
                continue
            self.draw_start(0, y, self._truncate(line, self.font, 9.5, self.content_w - 8),
                            self.font, 9.5, self.theme.dark)
            y -= 13
        return y - 6

    # ── Totals ──────────────────────────────────────────────────────────────

    def totals(self, y, lines):
        box_w = 270
        if not self.rtl:
            box_x = self.width - self.MARGIN - box_w
        else:
            box_x = self.MARGIN
        n = len(lines)
        box_h = 22 + n * 27
        top = y - box_h + 14
        ts = self.style.totals
        c, th = self.c, self.theme

        if ts == 'card':
            c.setFillColor(HexColor('#f7f9fb'))
            c.setStrokeColor(HexColor('#e5e8ec'))
            c.setLineWidth(0.75)
            c.roundRect(box_x, top, box_w, box_h, 5, stroke=1, fill=1)
            c.setFillColor(th.primary)
            c.rect(box_x, top + box_h - 3, box_w, 3, fill=1, stroke=0)
        elif ts == 'filled':
            c.setFillColor(th.secondary)
            c.roundRect(box_x, top, box_w, box_h, 4, stroke=0, fill=1)
        elif ts == 'bordered':
            c.setStrokeColor(th.secondary)
            c.setLineWidth(1)
            c.rect(box_x, top, box_w, box_h, stroke=1, fill=0)
        else:  # plain
            self.rule(y + 8, th.secondary, 1, x0=box_x, x1=box_x + box_w)

        filled = ts == 'filled'
        line_y = y - 6
        pad = 16
        for label, amount, is_main, is_alert in lines:
            if filled:
                lbl_color = white if is_main else HexColor('#c8d0d9')
                amt_color = HexColor('#fca5a5') if is_alert else white
            else:
                lbl_color = th.danger if is_alert else (th.secondary if is_main else th.gray)
                amt_color = th.primary if is_main else (th.danger if is_alert else th.dark)
            lsize = 11 if is_main else 9.5
            asize = 12 if is_main else 9.5
            lfont = self.font_bold if is_main else self.font
            afont = self.font_bold if is_main else self.font_medium
            # label at leading edge of box, amount at trailing edge
            if not self.rtl:
                self.text_at(box_x + pad, line_y, label, 'left', lfont, lsize, lbl_color)
                self.text_at(box_x + box_w - pad, line_y, self.loc.money(amount), 'right', afont, asize, amt_color)
            else:
                self.text_at(box_x + box_w - pad, line_y, label, 'right', lfont, lsize, lbl_color)
                self.text_at(box_x + pad, line_y, self.loc.money(amount), 'left', afont, asize, amt_color)
            if is_main and not filled:
                self.rule(line_y + 16, HexColor('#e5e8ec'), 0.75, x0=box_x + pad, x1=box_x + box_w - pad)
            line_y -= 27
        return top - 16

    # ── Amount highlight (receipts / expenses) ───────────────────────────────

    def amount_highlight(self, y, label, money_str):
        c, th = self.c, self.theme
        box_h = 56
        top = y - box_h
        c.setFillColor(_tint(th.primary, 0.88))
        c.setStrokeColor(_tint(th.primary, 0.6))
        c.setLineWidth(0.75)
        c.roundRect(self.MARGIN, top, self.content_w, box_h, 6, stroke=1, fill=1)
        c.setFillColor(th.primary)
        bar_w = 4
        c.rect(self.from_lead(0) - (0 if not self.rtl else bar_w), top, bar_w, box_h, fill=1, stroke=0)
        self.draw_start(20, top + box_h - 22, self.label(label), self.font_bold, 8.5, th.secondary)
        self.draw_start(20, top + 16, money_str, self.font_bold, 20, th.primary)
        return top - 20

    # ── Signatures ────────────────────────────────────────────────────────────

    def signatures(self, y, labels):
        c, th, m = self.c, self.theme, self.MARGIN
        n = len(labels)
        if n == 0:
            return y
        slot_w = (self.content_w - (n - 1) * 24) / n
        for i, lbl in enumerate(labels):
            x = m + i * (slot_w + 24)
            c.setStrokeColor(HexColor('#c8d0d9'))
            c.setLineWidth(0.75)
            c.line(x, y + 30, x + slot_w, y + 30)
            self.text_at(x + slot_w / 2, y + 14, lbl, 'center', self.font, 8.5, th.gray)
        return y - 10

    # ── Footer ────────────────────────────────────────────────────────────────

    def footer(self):
        th, w = self.theme, self.width
        text = (th.footer_text or self.company_name()).strip()
        fstyle = self.style.footer
        if fstyle == 'band':
            self.c.setFillColor(HexColor('#f4f6f9'))
            self.c.rect(0, 0, w, 30, fill=1, stroke=0)
            self.c.setFillColor(th.primary)
            self.c.rect(0, 30, w, 2, fill=1, stroke=0)
            self.draw_center(11, text, self.font, 7.5, th.gray)
        elif fstyle == 'minimal':
            self.draw_center(40, text, self.font, 7.5, th.gray)
        else:  # line
            self.rule(58, HexColor('#e5e8ec'))
            self.draw_center(44, text, self.font, 7.5, th.gray)


class PdfRenderer(DocRenderer):
    """Backward-compatible Arabic renderer for legacy financial reports
    (accounting/pdf_reporting.py). New documents use DocRenderer directly."""

    def __init__(self, canvas, width, height, theme, loc=None):
        from .i18n import Localizer
        super().__init__(canvas, width, height, theme, loc or Localizer('ar'))

    def ar(self, text):
        return '' if text is None else str(text)

    def draw_right(self, x, y, text, font=None, size=None):
        self.text_at(x, y, text, 'right', font or self.font, size or 10)

    def draw_string(self, x, y, text, font=None, size=None):
        self.text_at(x, y, text, 'left', font or self.font, size or 10)

    def draw_center_abs(self, x, y, text, font=None, size=None):
        self.text_at(x, y, text, 'center', font or self.font, size or 10)

    def draw_report_header(self, title_ar, date_range_text=None, page_num=1):
        y = self.header(title_ar, date_range_text or '', None)
        if page_num:
            self.text_at(self.from_lead(0), self.height - self.MARGIN - 4,
                         f'{self.loc.t("page")} {page_num}',
                         'left' if not self.rtl else 'right', self.font, 8, self.theme.gray)
        return y - 8
