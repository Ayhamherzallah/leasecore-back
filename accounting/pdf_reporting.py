import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

from pdf_templates.engine.branding import resolve_theme
from pdf_templates.engine.renderer import PdfRenderer


class FinancialPDFReport:
    def __init__(self, buffer, theme=None, building_id=None):
        self.buffer = buffer
        self.theme = theme or resolve_theme(building_id)
        self.c = canvas.Canvas(self.buffer, pagesize=A4)
        self.width, self.height = A4
        self.r = PdfRenderer(self.c, self.width, self.height, self.theme)

    def arabic(self, text):
        return self.r.ar(text)

    @property
    def font_name(self):
        return self.r.font

    @property
    def GOLD(self):
        return self.theme.primary

    @property
    def DARK(self):
        return self.theme.dark

    @property
    def GRAY(self):
        return self.theme.gray

    @property
    def LIGHT_GRAY(self):
        return self.theme.light_bg

    @property
    def RED(self):
        return self.theme.danger

    @property
    def GREEN(self):
        return self.theme.success

    def draw_header(self, title, date_range_text=None):
        return self.r.draw_report_header(title, date_range_text, self.c.getPageNumber())

    def draw_footer(self):
        self.r.draw_footer()

    def draw_summary_cards(self, cards, y):
        c = self.c
        width = self.width
        th = self.theme
        count = len(cards)
        if count == 0:
            return y
        card_width = (width - 100) / count - 10
        card_height = 60
        start_x = 50
        for i, card in enumerate(cards):
            x = start_x + i * (card_width + 15)
            c.setFillColor(th.light_bg)
            c.rect(x, y - card_height, card_width, card_height, fill=1, stroke=0)
            c.setStrokeColor(HexColor('#e2e8f0'))
            c.rect(x, y - card_height, card_width, card_height, fill=0, stroke=1)
            c.setFillColor(th.gray)
            c.setFont(self.font_name, 10)
            self.r.draw_right(x + card_width - 10, y - 20, card['label'])
            val_color = card.get('color', th.dark)
            c.setFillColor(val_color)
            c.setFont(self.font_name, 16)
            c.drawRightString(x + card_width - 10, y - 45, str(card['value']))
        return y - card_height - 30

    def draw_section_title(self, title, y):
        c = self.c
        width = self.width
        c.setFillColor(self.theme.dark)
        c.setFont(self.font_name, 14)
        self.r.draw_right(width - 50, y, title)
        c.setStrokeColor(HexColor('#e2e8f0'))
        c.line(50, y - 5, width - 50, y - 5)
        return y - 25

    def draw_table(self, columns, data, y):
        c = self.c
        width = self.width
        th = self.theme

        curr = width - 50
        x_positions = []
        for col in columns:
            curr -= col['width']
            x_positions.append({'col': col, 'x': curr, 'w': col['width']})
            c.setFillColor(th.light_bg)
            c.rect(curr, y - 20, col['width'], 22, fill=1, stroke=0)
            c.setFillColor(th.dark)
            c.setFont(self.font_name, 10)
            self.r.draw_right(curr + col['width'] - 5, y - 12, col['header'])

        y -= 25
        c.setFont(self.font_name, 10)
        for row in data:
            if y < 80:
                self.c.showPage()
                self.draw_header('تابع التقرير...')
                y = self.height - 180
            for pos in x_positions:
                col = pos['col']
                raw_val = row.get(col['key'], '')
                val = col['format'](raw_val) if 'format' in col else str(raw_val)
                if 'color_func' in col:
                    c.setFillColor(col['color_func'](raw_val))
                else:
                    c.setFillColor(th.dark)
                self.r.draw_right(pos['x'] + pos['w'] - 5, y - 10, val)
            c.setStrokeColor(HexColor('#f1f5f9'))
            c.line(50, y - 15, width - 50, y - 15)
            y -= 25
        return y - 20

    def draw_detailed_gl_table(self, groups, y):
        c = self.c
        width = self.width
        th = self.theme

        c.setFillColor(th.dark)
        c.setFont(self.font_name, 10)
        self.r.draw_right(width - 50, y, 'التاريخ')
        self.r.draw_right(width - 140, y, 'البيان')
        self.r.draw_right(120, y, 'المبلغ')
        c.setStrokeColor(HexColor('#e2e8f0'))
        c.line(50, y - 5, width - 50, y - 5)
        y -= 25

        for group in groups:
            if y < 80:
                self.c.showPage()
                self.draw_header('تابع...')
                y = self.height - 180

            c.setFillColor(th.light_bg)
            c.rect(50, y - 24, width - 100, 24, fill=1, stroke=0)
            c.setFillColor(th.dark)
            c.setFont(self.font_name, 11)
            self.r.draw_right(width - 60, y - 17, group.get('account', ''))
            amount_val = group.get('amount', 0)
            c.drawRightString(120, y - 17, f'{float(amount_val):,.2f}')
            y -= 24

            c.setFont(self.font_name, 9)
            for row in group.get('details', []):
                if y < 50:
                    self.c.showPage()
                    self.draw_header('تابع...')
                    y = self.height - 180
                c.setFillColor(th.gray)
                c.drawRightString(width - 50, y - 15, str(row.get('date', '')))
                desc = row.get('description', '')
                if len(desc) > 55:
                    desc = desc[:52] + '...'
                c.setFillColor(th.dark)
                self.r.draw_right(width - 140, y - 15, desc)
                amt = row.get('amount', 0)
                c.drawRightString(120, y - 15, f'{float(amt):,.2f}')
                c.setStrokeColor(HexColor('#f8fafc'))
                c.line(50, y - 25, width - 50, y - 25)
                y -= 25
            y -= 10
        return y

    def save(self):
        self.c.save()
        self.buffer.seek(0)
        return self.buffer


def _building_id_from_request(building_id):
    if building_id:
        try:
            return int(building_id)
        except (TypeError, ValueError):
            pass
    return None


def generate_profit_loss_pdf(data, date_range_text, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('تقرير الأرباح والخسائر - تفصيلي', date_range_text)
    y = report.height - 180
    cards = [
        {'label': 'صافي الربح', 'value': f"{data['net_profit']:,.2f}",
         'color': report.GREEN if data['net_profit'] >= 0 else report.RED},
        {'label': 'إجمالي المصروفات', 'value': f"{data['total_expenses']:,.2f}", 'color': report.RED},
        {'label': 'إجمالي الإيرادات', 'value': f"{data['total_revenue']:,.2f}", 'color': report.GREEN},
    ]
    y = report.draw_summary_cards(cards, y)
    y = report.draw_section_title('تفاصيل الإيرادات', y)
    y = report.draw_detailed_gl_table([d for d in data['revenue_breakdown'] if d['amount'] != 0], y)
    y = report.draw_section_title('تفاصيل المصروفات', y)
    y = report.draw_detailed_gl_table([d for d in data['expense_breakdown'] if d['amount'] != 0], y)
    report.draw_footer()
    return report.save()


def generate_revenue_pdf(data, date_range_text, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('تقرير الإيرادات التفصيلي', date_range_text)
    y = report.height - 180
    y = report.draw_summary_cards([{'label': 'إجمالي الإيرادات', 'value': f"{data['total_revenue']:,.2f}", 'color': report.GREEN}], y)
    y = report.draw_section_title('الإيرادات حسب الحساب', y)
    y = report.draw_detailed_gl_table(data['by_account'], y)
    if y < 150:
        report.c.showPage()
        report.draw_header('تابع الإيرادات')
        y = report.height - 180
    y = report.draw_section_title('الإيرادات حسب المستأجر', y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'المستأجر', 'key': 'tenant__name', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_tenant'], y)
    if y < 150:
        report.c.showPage()
        report.draw_header('تابع الإيرادات')
        y = report.height - 180
    y = report.draw_section_title('الإيرادات حسب الوحدة', y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'الوحدة', 'key': 'contract__unit__unit_number', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_unit'], y)
    report.draw_footer()
    return report.save()


def generate_expense_report_pdf(data, date_range_text, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('تقرير المصروفات التفصيلي', date_range_text)
    y = report.height - 180
    y = report.draw_summary_cards([{'label': 'إجمالي المصروفات', 'value': f"{data['total_expenses']:,.2f}", 'color': report.RED}], y)
    y = report.draw_section_title('المصروفات حسب التصنيف', y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'التصنيف', 'key': 'category__name', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_category'], y)
    if y < 150:
        report.c.showPage()
        report.draw_header('تابع المصروفات')
        y = report.height - 180
    y = report.draw_section_title('المصروفات حسب الوحدة', y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'الوحدة', 'key': 'unit__unit_number', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_unit'], y)
    if y < 150:
        report.c.showPage()
        report.draw_header('تابع المصروفات')
        y = report.height - 180
    y = report.draw_section_title('تفاصيل حسابات GL', y)
    y = report.draw_detailed_gl_table(data['by_account'], y)
    report.draw_footer()
    return report.save()


def generate_cash_flow_pdf(data, date_range_text, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('تقرير التدفقات النقدية', date_range_text)
    y = report.height - 180
    cards = [
        {'label': 'صافي التدفق', 'value': f"{data['net']:,.2f}", 'color': report.GREEN if data['net'] >= 0 else report.RED},
        {'label': 'إجمالي المصروفات', 'value': f"{data['total_out']:,.2f}", 'color': report.RED},
        {'label': 'إجمالي المقبوضات', 'value': f"{data['total_in']:,.2f}", 'color': report.GREEN},
    ]
    y = report.draw_summary_cards(cards, y)
    if data.get('breakdown'):
        y = report.draw_section_title('التدفق الزمني', y)
        cols = [
            {'header': 'الصافي', 'key': 'net', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
            {'header': 'خارج', 'key': 'out', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
            {'header': 'داخل', 'key': 'in', 'width': 100, 'format': lambda x: f'{float(x):,.2f}'},
            {'header': 'التاريخ', 'key': 'date', 'width': 100},
        ]
        y = report.draw_table(cols, data['breakdown'], y)
    report.draw_footer()
    return report.save()


def generate_tenant_report_pdf(data, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('ملخص أرصدة المستأجرين', f'كما في {datetime.date.today()}')
    y = report.height - 180
    cols = [
        {'header': 'آخر دفعة', 'key': 'last_payment_date', 'width': 80, 'format': lambda x: str(x) if x else '-'},
        {'header': 'الرصيد', 'key': 'balance', 'width': 80, 'format': lambda x: f'{float(x):,.2f}',
         'color_func': lambda x: report.RED if float(x) > 0 else report.GREEN},
        {'header': 'مدفوع', 'key': 'total_paid', 'width': 80, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'مفوتر', 'key': 'total_invoiced', 'width': 80, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'المستأجر', 'key': 'name', 'width': 150},
    ]
    report.draw_table(cols, data, y)
    report.draw_footer()
    return report.save()


def generate_unit_report_pdf(data, date_range_text, building_id=None):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer, building_id=_building_id_from_request(building_id))
    report.draw_header('تقرير أداء الوحدات', date_range_text)
    y = report.height - 180
    cols = [
        {'header': 'الصافي', 'key': 'net', 'width': 90, 'format': lambda x: f'{float(x):,.2f}',
         'color_func': lambda x: report.GREEN if float(x) >= 0 else report.RED},
        {'header': 'المصروفات', 'key': 'expenses', 'width': 90, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'الإيرادات', 'key': 'revenue', 'width': 90, 'format': lambda x: f'{float(x):,.2f}'},
        {'header': 'الحالة', 'key': 'status', 'width': 80},
        {'header': 'الوحدة', 'key': 'unit', 'width': 80},
    ]
    report.draw_table(cols, data, y)
    report.draw_footer()
    return report.save()
