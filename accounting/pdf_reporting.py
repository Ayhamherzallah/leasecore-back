import os
from io import BytesIO
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
import arabic_reshaper
from bidi.algorithm import get_display
import datetime

class FinancialPDFReport:
    def __init__(self, buffer):
        self.buffer = buffer
        self.c = canvas.Canvas(self.buffer, pagesize=A4)
        self.width, self.height = A4
        self.font_name = 'Helvetica'
        self._register_fonts()
        
        # Theme Colors
        self.GOLD = HexColor('#C5A059')
        self.DARK = HexColor('#1F1F1F')
        self.GRAY = HexColor('#757575')
        self.LIGHT_GRAY = HexColor('#F9F9F9')
        self.RED = HexColor('#EF4444')
        self.GREEN = HexColor('#10B981')

    def _register_fonts(self):
        try:
            possible_fonts = [
                 os.path.join(settings.BASE_DIR, 'assets', 'fonts', 'Amiri-Regular.ttf'),
                 '/System/Library/Fonts/Supplemental/Arial.ttf',
                 '/Library/Fonts/Arial.ttf',
                 '/System/Library/Fonts/Arial.ttf',
                 '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            ]
            for path in possible_fonts:
                if os.path.exists(path):
                    pdfmetrics.registerFont(TTFont('Arabic', path))
                    self.font_name = 'Arabic'
                    break
        except:
            pass

    def arabic(self, text):
        if not text: return ""
        text = str(text)
        if self.font_name != 'Arabic': return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    def draw_header(self, title, date_range_text=None):
        c = self.c
        width, height = self.width, self.height
        
        # --- Header Band ---
        c.setFillColor(self.DARK) 
        c.rect(0, height - 140, width, 140, fill=1, stroke=0)
        
        c.setFillColor(self.GOLD)
        c.rect(0, height - 145, width, 5, fill=1, stroke=0)

        # Company Title (Right)
        c.setFillColor(self.GOLD)
        c.setFont(self.font_name, 32)
        c.drawRightString(width - 50, height - 70, self.arabic("أبـو رخيـة بـلازا"))
        
        c.setFillColor(colors.white)
        c.setFont(self.font_name, 14)
        c.drawRightString(width - 50, height - 100, self.arabic("إدارة العقارات والاستثمارات"))

        # Report Title (Left)
        c.setFillColor(colors.white)
        c.setFont(self.font_name, 24)
        c.drawString(50, height - 70, self.arabic(title))
        
        # Meta Info
        c.setFont(self.font_name, 11)
        c.setFillColor(colors.white)
        if date_range_text:
            c.drawString(50, height - 100, self.arabic(f"الفترة: {date_range_text}"))
        else:
            c.drawString(50, height - 100, self.arabic(f"تاريخ: {datetime.date.today()}"))

        # Page Number
        c.setFont(self.font_name, 10)
        c.setFillColor(self.GRAY)
        c.drawRightString(width - 50, height - 130, self.arabic(f"صفحة {c.getPageNumber()}"))

    def draw_footer(self):
        c = self.c
        width = self.width
        footer_y = 50
        
        c.setStrokeColor(self.GOLD)
        c.setLineWidth(1)
        c.line(50, footer_y + 30, width - 50, footer_y + 30)
        
        c.setFillColor(self.GRAY)
        c.setFont(self.font_name, 9)
        c.drawCentredString(width / 2, footer_y + 10, self.arabic("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))

    def draw_summary_cards(self, cards, y):
        """
        Draws 2-4 summary cards in a row.
        cards: list of {'label': str, 'value': str/float, 'color': HexColor}
        """
        c = self.c
        width = self.width
        count = len(cards)
        if count == 0: return y
        
        card_width = (width - 100) / count - 10
        card_height = 60
        start_x = 50
        
        # RTL: Draw from right to left or just standard? 
        # UI is Right-to-Left essentially for Arabic, but blocks can be standard.
        # Let's simple left-to-right but with Arabic text inside.
        
        for i, card in enumerate(cards):
            x = start_x + i * (card_width + 15)
            
            # Card Bg
            c.setFillColor(self.LIGHT_GRAY)
            c.rect(x, y - card_height, card_width, card_height, fill=1, stroke=0)
            
            # Label (Top Right of card)
            c.setFillColor(self.GRAY)
            c.setFont(self.font_name, 10)
            c.drawRightString(x + card_width - 10, y - 20, self.arabic(card['label']))
            
            # Value (Big, Centered or Right)
            val_color = card.get('color', self.DARK)
            c.setFillColor(val_color)
            c.setFont(self.font_name, 16)
            c.drawRightString(x + card_width - 10, y - 45, str(card['value'])) # Value usually number
            
        return y - card_height - 30

    def draw_section_title(self, title, y):
        c = self.c
        width = self.width
        c.setFillColor(self.DARK)
        c.setFont(self.font_name, 14)
        c.drawRightString(width - 50, y, self.arabic(title))
        c.setStrokeColor(self.LIGHT_GRAY)
        c.line(50, y - 5, width - 50, y - 5)
        return y - 25

    def draw_table(self, columns, data, y):
        """
        columns: list of {'header': str, 'key': str, 'width': int, 'format': func}
        """
        c = self.c
        width = self.width
        
        # Header
        col_x = width - 50 # Starting from Right
        header_height = 25
        
        c.setFillColor(self.LIGHT_GRAY)
        c.rect(50, y - header_height + 5, width - 100, header_height, fill=1, stroke=0)
        
        current_x = width - 50
        c.setFillColor(self.DARK)
        c.setFont(self.font_name, 10)
        
        # Headers
        for col in columns:
            w = col['width']
            # Center of column
            # c.drawRightString(current_x - 10, y - 10, self.arabic(col['header']))
            # Actually easier to manage standard x coords if we define them relative to right
            
            # Let's just use specific X mapping logic
            pass

        # Simplified Table Matrix Logic:
        # Define X positions for each column center or right align
        # Total width = 595 (A4). Margins 50. Usable = 495.
        
        # Calulate X positions
        x_positions = []
        curr = width - 50
        for col in columns:
            curr -= col['width']
            x_positions.append({'col': col, 'x': curr, 'w': col['width']})
            
            # Draw Header
            c.setFillColor(self.DARK)
            c.setFont(self.font_name, 10) # bold?
            c.drawRightString(curr + col['width'] - 5, y - 12, self.arabic(col['header']))

        y -= 25
        
        # Rows
        c.setFont(self.font_name, 10)
        
        for row in data:
            if y < 80:
                c.showPage()
                self.draw_header("تابع تقرير...") # Simple header on follow up pages
                y = self.height - 180
            
            # Draw Cells
            for pos in x_positions:
                col = pos['col']
                raw_val = row.get(col['key'], '')
                
                # Format
                if 'format' in col:
                    val = col['format'](raw_val)
                else:
                    val = str(raw_val)
                
                # Color
                if 'color_func' in col:
                    c.setFillColor(col['color_func'](raw_val))
                else:
                    c.setFillColor(self.DARK)

                c.drawRightString(pos['x'] + pos['w'] - 5, y - 10, self.arabic(val))

            # Line
            c.setStrokeColor(HexColor('#EEEEEE'))
            c.line(50, y - 15, width - 50, y - 15)
            y -= 25
            
        return y - 20

    def draw_detailed_gl_table(self, groups, y):
        c = self.c
        width = self.width
        
        # Main Header for the Detailed Section
        c.setFillColor(self.DARK)
        c.setFont(self.font_name, 10)
        c.drawRightString(width - 50, y, self.arabic("التاريخ"))
        c.drawRightString(width - 140, y, self.arabic("البيان"))
        c.drawRightString(120, y, self.arabic("المبلغ"))
        
        c.setStrokeColor(self.LIGHT_GRAY)
        c.line(50, y - 5, width - 50, y - 5)
        y -= 25
        
        for group in groups:
            # Check for page break (giving enough space for header + 1 row)
            if y < 80:
                 c.showPage(); self.draw_header("تابع..."); y = self.height - 180
            
            # Parent Row (Account Header)
            # Modern styling: Soft background, clear bold text
            c.setFillColor(HexColor('#F3F4F6')) 
            c.rect(50, y - 24, width - 100, 24, fill=1, stroke=0)
            
            c.setFillColor(self.DARK)
            c.setFont(self.font_name, 11)
            # Account Name
            c.drawRightString(width - 60, y - 17, self.arabic(group.get('account', '')))
            
            # Group Total
            amount_val = group.get('amount', 0)
            c.drawRightString(120, y - 17, f"{float(amount_val):,.2f}")
            
            y -= 24 
            
            # Child Rows
            c.setFont(self.font_name, 9)
            details = group.get('details', [])
            for row in details:
                if y < 50:
                    c.showPage(); self.draw_header("تابع..."); y = self.height - 180
                
                # 1. Date (Gray, Right Aligned)
                c.setFillColor(self.GRAY)
                dt = str(row.get('date', ''))
                c.drawRightString(width - 50, y - 15, dt)
                
                # 2. Description (Dark, Right Aligned at 450ish)
                c.setFillColor(self.DARK)
                desc = row.get('description', '')
                # Truncate text to prevent overflow into Amount column
                # Max width approx 300px. Approx 50-60 characters.
                if len(desc) > 55:
                    desc = desc[:52] + "..."
                c.drawRightString(width - 140, y - 15, self.arabic(desc))
                
                # 3. Amount (Dark, aligned with header)
                amt = row.get('amount', 0)
                c.drawRightString(120, y - 15, f"{float(amt):,.2f}")
                
                # Row separator
                c.setStrokeColor(HexColor('#F9FAFB'))
                c.line(50, y - 25, width - 50, y - 25)
                
                y -= 25 # More vertical breathing room
            
            y -= 10 # Spacing between groups
            
        return y

    def save(self):
        self.c.save()
        self.buffer.seek(0)
        return self.buffer

# --- Report Generators ---

def generate_profit_loss_pdf(data, date_range_text):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    
    # 1. Header
    report.draw_header("تقرير الأرباح والخسائر - تفصيلي", date_range_text)
    y = report.height - 180
    
    # 2. Summary Cards
    cards = [
        {'label': 'صافي الربح', 'value': f"{data['net_profit']:,.2f}", 'color': report.GREEN if data['net_profit'] >= 0 else report.RED},
        {'label': 'إجمالي المصروفات', 'value': f"{data['total_expenses']:,.2f}", 'color': report.RED},
        {'label': 'إجمالي الإيرادات', 'value': f"{data['total_revenue']:,.2f}", 'color': report.GREEN},
    ]
    y = report.draw_summary_cards(cards, y)
    
    # 3. Revenue Section
    y = report.draw_section_title("تفاصيل الإيرادات", y)
    rev_data = [d for d in data['revenue_breakdown'] if d['amount'] != 0]
    y = report.draw_detailed_gl_table(rev_data, y)
    
    # 4. Expense Section
    y = report.draw_section_title("تفاصيل المصروفات", y)
    exp_data = [d for d in data['expense_breakdown'] if d['amount'] != 0]
    y = report.draw_detailed_gl_table(exp_data, y)
    
    report.draw_footer()
    return report.save()

def generate_revenue_pdf(data, date_range_text):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    report.draw_header("تقرير الإيرادات التفصيلي", date_range_text)
    y = report.height - 180
    
    # Summary
    cards = [{'label': 'إجمالي الإيرادات', 'value': f"{data['total_revenue']:,.2f}", 'color': report.GREEN}]
    y = report.draw_summary_cards(cards, y)

    # By Account (Detailed)
    y = report.draw_section_title("الإيرادات حسب الحساب", y)
    y = report.draw_detailed_gl_table(data['by_account'], y)
    
    # By Tenant
    if y < 150: 
        report.c.showPage(); report.draw_header("تابع الإيرادات"); y = report.height - 180

    y = report.draw_section_title("الإيرادات حسب المستأجر", y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'المستأجر', 'key': 'tenant__name', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_tenant'], y)
    
    # By Unit
    if y < 150: 
        report.c.showPage(); report.draw_header("تابع الإيرادات"); y = report.height - 180
        
    y = report.draw_section_title("الإيرادات حسب الوحدة", y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'الوحدة', 'key': 'contract__unit__unit_number', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_unit'], y)
    
    report.draw_footer()
    return report.save()

def generate_expense_report_pdf(data, date_range_text):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    report.draw_header("تقرير المصروفات التفصيلي", date_range_text)
    y = report.height - 180
    
    # Summary
    cards = [{'label': 'إجمالي المصروفات', 'value': f"{data['total_expenses']:,.2f}", 'color': report.RED}]
    y = report.draw_summary_cards(cards, y)
    
    # By Category
    y = report.draw_section_title("المصروفات حسب التصنيف", y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'التصنيف', 'key': 'category__name', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_category'], y)
    
    # By Unit
    if y < 150: 
        report.c.showPage(); report.draw_header("تابع المصروفات"); y = report.height - 180
        
    y = report.draw_section_title("المصروفات حسب الوحدة", y)
    cols = [
        {'header': 'المبلغ', 'key': 'total', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'الوحدة', 'key': 'unit__unit_number', 'width': 300},
    ]
    y = report.draw_table(cols, data['by_unit'], y)

    # By GL Account (Detailed)
    if y < 150: 
        report.c.showPage(); report.draw_header("تابع المصروفات"); y = report.height - 180
        
    y = report.draw_section_title("تفاصيل حسابات GL", y)
    y = report.draw_detailed_gl_table(data['by_account'], y)
    
    report.draw_footer()
    return report.save()

def generate_cash_flow_pdf(data, date_range_text):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    report.draw_header("تقرير التدفقات النقدية", date_range_text)
    y = report.height - 180
    
    cards = [
        {'label': 'صافي التدفق', 'value': f"{data['net']:,.2f}", 'color': report.GREEN if data['net'] >= 0 else report.RED},
        {'label': 'إجمالي المصروفات', 'value': f"{data['total_out']:,.2f}", 'color': report.RED},
        {'label': 'إجمالي المقبوضات', 'value': f"{data['total_in']:,.2f}", 'color': report.GREEN},
    ]
    y = report.draw_summary_cards(cards, y)
    
    # Detailed section not really available in aggregate data, so we just show standard text or disclaimer
    # Or break it down if data had it. Current get_cash_flow only returns totals. `breakdown` key exists?
    # View `ReportingService.get_cash_flow` logic... it returns list of dicts: month/day breakdown?
    # Earlier I implemented it returning simplified object?
    # Checked `reporting.py` in memory: get_cash_flow(start, end).
    
    # Let's assume user wants the month-by-month or day-by-day if useful.
    # Currently frontend graph uses `breakdown`.
    # I'll check `ReportingService` return structure properly later. assuming `breakdown` exists.
    
    if 'breakdown' in data and data['breakdown']:
        y = report.draw_section_title("التدفق الزمني", y)
        cols = [
            {'header': 'الصافي', 'key': 'net', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
            {'header': 'خارج', 'key': 'out', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
            {'header': 'داخل', 'key': 'in', 'width': 100, 'format': lambda x: f"{float(x):,.2f}"},
            {'header': 'التاريخ', 'key': 'date', 'width': 100},
        ]
        y = report.draw_table(cols, data['breakdown'], y)

    report.draw_footer()
    return report.save()

def generate_tenant_report_pdf(data):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    report.draw_header("ملخص أرصدة المستأجرين", f"كما في {datetime.date.today()}")
    y = report.height - 180
    
    cols = [
        {'header': 'آخر دفعة', 'key': 'last_payment_date', 'width': 80, 'format': lambda x: str(x) if x else "-"},
        {'header': 'الرصيد', 'key': 'balance', 'width': 80, 'format': lambda x: f"{float(x):,.2f}", 'color_func': lambda x: report.RED if float(x) > 0 else report.GREEN},
        {'header': 'مدفوع', 'key': 'total_paid', 'width': 80, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'مفوتر', 'key': 'total_invoiced', 'width': 80, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'المستأجر', 'key': 'name', 'width': 150},
    ]
    y = report.draw_table(cols, data, y)
    
    report.draw_footer()
    return report.save()

def generate_unit_report_pdf(data, date_range_text):
    buffer = BytesIO()
    report = FinancialPDFReport(buffer)
    report.draw_header("تقرير أداء الوحدات", date_range_text)
    y = report.height - 180
    
    cols = [
        {'header': 'الصافي', 'key': 'net', 'width': 90, 'format': lambda x: f"{float(x):,.2f}", 'color_func': lambda x: report.GREEN if float(x) >= 0 else report.RED},
        {'header': 'المصروفات', 'key': 'expenses', 'width': 90, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'الإيرادات', 'key': 'revenue', 'width': 90, 'format': lambda x: f"{float(x):,.2f}"},
        {'header': 'الحالة', 'key': 'status', 'width': 80},
        {'header': 'الوحدة', 'key': 'unit', 'width': 80},
    ]
    y = report.draw_table(cols, data, y)
    
    report.draw_footer()
    return report.save()
