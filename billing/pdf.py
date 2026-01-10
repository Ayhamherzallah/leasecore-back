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

def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Fonts
    font_name = 'Helvetica' # Default standard PDF font
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
                font_name = 'Arabic'
                break
    except:
        pass 

    # Branding Colors
    GOLD = HexColor('#C5A059')
    DARK = HexColor('#1F1F1F')
    GRAY = HexColor('#757575')
    LIGHT_GRAY = HexColor('#F9F9F9')

    def arabic(text):
        if font_name != 'Arabic': return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    # --- Header Band ---
    c.setFillColor(DARK) 
    c.rect(0, height - 140, width, 140, fill=1, stroke=0)
    
    c.setFillColor(GOLD)
    c.rect(0, height - 145, width, 5, fill=1, stroke=0)

    # Title (Right)
    c.setFillColor(GOLD)
    c.setFont(font_name, 32)
    c.drawRightString(width - 50, height - 70, arabic("أبـو رخيـة بـلازا"))
    
    c.setFillColor(colors.white)
    c.setFont(font_name, 14)
    c.drawRightString(width - 50, height - 100, arabic("إدارة العقارات والاستثمارات"))

    # Invoice Label (Left)
    c.setFillColor(colors.white)
    c.setFont(font_name, 24)
    c.drawString(50, height - 70, arabic("فاتورة مبيعات"))
    
    c.setFont(font_name, 12)
    c.setFillColor(colors.white)
    c.drawString(50, height - 100, f"#{invoice.invoice_number}")

    # --- Info Grid ---
    y = height - 200
    
    # Dates (Left)
    c.setFillColor(GRAY)
    c.setFont(font_name, 10)
    c.drawRightString(180, y, arabic("تاريخ الإصدار"))
    c.drawRightString(180, y - 30, arabic("تاريخ الاستحقاق"))
    
    c.setFillColor(DARK)
    c.setFont(font_name, 10)
    c.drawString(50, y, str(invoice.issue_date))
    c.drawString(50, y - 30, str(invoice.due_date))

    # Bill To (Right)
    c.setFillColor(GRAY)
    c.setFont(font_name, 12)
    c.drawRightString(width - 50, y, arabic("فوتـرة إلـى العميـل:"))
    
    y -= 25
    c.setFillColor(DARK)
    c.setFont(font_name, 16)
    tenant_name = invoice.contract.tenant.name if invoice.contract else "عميل نقدي"
    c.drawRightString(width - 50, y, arabic(tenant_name))
    
    # --- Table ---
    y -= 80
    
    # Header
    c.setFillColor(LIGHT_GRAY)
    c.rect(40, y - 10, width - 80, 35, fill=1, stroke=0)
    
    c.setFillColor(GOLD)
    c.setFont(font_name, 11)
    
    c.drawRightString(width - 60, y, arabic("البيان / الوصف"))
    c.drawString(60, y, arabic("المبلغ (دينار اردني)"))
    
    # Row
    y -= 50
    c.setFillColor(DARK)
    c.setFont(font_name, 12)
    
    invoice_type_map = {
        'RENT': 'دفعة إيجار وحدة',
        'UTILITY': 'فواتير خدمات / كهرباء',
        'SERVICE': 'رسوم خدمات صيانة',
        'PENALTY': 'غرامة تأخير'
    }
    desc_text = invoice_type_map.get(invoice.invoice_type, 'خدمات عقارية')
    if invoice.contract and invoice.contract.unit:
        desc_text += f" - وحدة رقم {invoice.contract.unit.unit_number}"
        
    c.drawRightString(width - 60, y, arabic(desc_text))
    c.drawString(60, y, f"{invoice.total_amount:,.2f}")
    
    c.setStrokeColor(HexColor('#EEEEEE'))
    c.line(40, y - 15, width - 40, y - 15)

    # --- Totals ---
    y -= 60
    
    c.setFillColor(GOLD)
    c.rect(40, y - 20, 200, 40, fill=1, stroke=0)
    
    c.setFillColor(colors.white)
    c.setFont(font_name, 14)
    # Swapped positions: Label Right, Value Left
    c.drawRightString(230, y - 5, arabic("الإجمالي المستحق"))
    c.drawString(50, y - 5, f"{invoice.total_amount:,.2f}")

    # --- Footer ---
    footer_y = 50
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(50, footer_y + 30, width - 50, footer_y + 30)
    
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawCentredString(width / 2, footer_y + 10, arabic("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))
    c.drawCentredString(width / 2, footer_y - 5, arabic("شكرًا لتعاملكم معنا"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def generate_receipt_pdf(payment):
    """
    Generates a Payment Receipt (Kabd Sond) PDF.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Fonts Check
    font_name = 'Helvetica'
    try:
        possible_fonts = [
             os.path.join(settings.BASE_DIR, 'assets', 'fonts', 'Amiri-Regular.ttf'),
             '/System/Library/Fonts/Supplemental/Arial.ttf',
             '/Library/Fonts/Arial.ttf'
        ]
        for path in possible_fonts:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont('Arabic', path))
                font_name = 'Arabic'
                break
    except:
        pass 

    GOLD = HexColor('#C5A059')
    DARK = HexColor('#1F1F1F')
    GRAY = HexColor('#757575')
    LIGHT_GRAY = HexColor('#F9F9F9')

    def arabic(text):
        if font_name != 'Arabic': return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    # --- Header ---
    c.setFillColor(DARK) 
    c.rect(0, height - 140, width, 140, fill=1, stroke=0)
    
    c.setFillColor(GOLD)
    c.rect(0, height - 145, width, 5, fill=1, stroke=0)

    # Title
    c.setFillColor(GOLD)
    c.setFont(font_name, 32)
    c.drawRightString(width - 50, height - 70, arabic("أبـو رخيـة بـلازا"))
    
    c.setFillColor(colors.white)
    c.setFont(font_name, 14)
    c.drawRightString(width - 50, height - 100, arabic("إدارة العقارات والاستثمارات"))

    # Receipt Label
    c.setFillColor(colors.white)
    c.setFont(font_name, 24)
    c.drawString(50, height - 70, arabic("سند قبض"))
    
    c.setFont(font_name, 12)
    c.setFillColor(colors.white)
    ref_text = payment.reference_number if payment.reference_number else str(payment.id)
    c.drawString(50, height - 100, f"Ref: {ref_text}")

    # --- Info Grid ---
    y = height - 200
    
    # Date
    c.setFillColor(GRAY)
    c.setFont(font_name, 12)
    c.drawRightString(width - 50, y, arabic("التاريخ:"))
    c.setFillColor(DARK)
    c.drawString(width - 200, y, str(payment.payment_date))

    # Payer
    y -= 30
    c.setFillColor(GRAY)
    c.drawRightString(width - 50, y, arabic("استلمنا من السيد/السادة:"))
    c.setFillColor(DARK)
    
    tenant_name = payment.invoice.contract.tenant.name if (payment.invoice and payment.invoice.contract) else "عميل نقدي"
    c.drawRightString(width - 50, y - 25, arabic(tenant_name))
    
    # Amount
    y -= 60
    c.setFillColor(GRAY)
    c.drawRightString(width - 50, y, arabic("مبلغ وقدره:"))
    
    c.setFillColor(GOLD)
    c.setFont(font_name, 18)
    # Swapped: Text + Number
    c.drawRightString(width - 50, y - 30, arabic("دينار اردني") + f" {payment.amount:,.2f}")
    
    # Details Box
    y -= 80
    c.setFillColor(LIGHT_GRAY)
    c.rect(40, y - 60, width - 80, 80, fill=1, stroke=0)
    
    c.setFillColor(DARK)
    c.setFont(font_name, 12)
    
    # Payment Method
    method_map = {'CASH': 'نقدًا', 'CHECK': 'شيك', 'TRANSFER': 'تحويل بنكي', 'POS': 'شبكة'}
    method_ar = method_map.get(payment.payment_method, payment.payment_method)
    
    c.drawRightString(width - 60, y - 20, arabic(f"طريقة الدفع: {method_ar}"))
         
    # Invoice Ref
    c.drawString(60, y - 20, f"Ref Invoice #{payment.invoice.invoice_number}")

    # --- Footer ---
    footer_y = 50
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(50, footer_y + 30, width - 50, footer_y + 30)
    
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawCentredString(width / 2, footer_y + 10, arabic("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))
    c.drawCentredString(width / 2, footer_y - 5, arabic("شكرًا لتعاملكم معنا"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_expense_pdf(expense):
    """
    Generates an Expense Voucher (Sanad Sarf) PDF.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Fonts Check
    font_name = 'Helvetica'
    try:
        possible_fonts = [
             os.path.join(settings.BASE_DIR, 'assets', 'fonts', 'Amiri-Regular.ttf'),
             '/System/Library/Fonts/Supplemental/Arial.ttf',
             '/Library/Fonts/Arial.ttf',
             '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        ]
        for path in possible_fonts:
            if os.path.exists(path):
                pdfmetrics.registerFont(TTFont('Arabic', path))
                font_name = 'Arabic'
                break
    except:
        pass 

    GOLD = HexColor('#C5A059')
    DARK = HexColor('#1F1F1F')
    GRAY = HexColor('#757575')
    LIGHT_GRAY = HexColor('#F9F9F9')

    def arabic(text):
        if font_name != 'Arabic': return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    # --- Header ---
    c.setFillColor(DARK) 
    c.rect(0, height - 140, width, 140, fill=1, stroke=0)
    
    c.setFillColor(GOLD)
    c.rect(0, height - 145, width, 5, fill=1, stroke=0)

    # Title
    c.setFillColor(GOLD)
    c.setFont(font_name, 32)
    c.drawRightString(width - 50, height - 70, arabic("أبـو رخيـة بـلازا"))
    
    c.setFillColor(colors.white)
    c.setFont(font_name, 14)
    c.drawRightString(width - 50, height - 100, arabic("إدارة العقارات والاستثمارات"))

    # Voucher Label
    c.setFillColor(colors.white)
    c.setFont(font_name, 24)
    c.drawString(50, height - 70, arabic("سند صرف"))
    
    c.setFont(font_name, 12)
    c.setFillColor(colors.white)
    ref_text = expense.invoice_reference if expense.invoice_reference else str(expense.id)
    c.drawString(50, height - 100, f"Ref: {ref_text}")

    # --- Info Grid ---
    y = height - 200
    
    # Date
    c.setFillColor(GRAY)
    c.setFont(font_name, 12)
    c.drawRightString(width - 50, y, arabic("التاريخ:"))
    c.setFillColor(DARK)
    c.drawString(width - 200, y, str(expense.expense_date))

    # Payee (Vendor)
    y -= 30
    c.setFillColor(GRAY)
    c.drawRightString(width - 50, y, arabic("صرفنا إلى السيد/السادة:"))
    c.setFillColor(DARK)
    
    payee_name = expense.vendor_name if expense.vendor_name else "نثريات / غير محدد"
    c.drawRightString(width - 50, y - 25, arabic(payee_name))
    
    # Amount
    y -= 60
    c.setFillColor(GRAY)
    c.drawRightString(width - 50, y, arabic("مبلغ وقدره:"))
    
    c.setFillColor(GOLD)
    c.setFont(font_name, 18)
    c.drawRightString(width - 50, y - 30, arabic("دينار اردني") + f" {expense.amount:,.2f}")
    
    # Details Box
    y -= 80
    c.setFillColor(LIGHT_GRAY)
    c.rect(40, y - 60, width - 80, 80, fill=1, stroke=0)
    
    c.setFillColor(DARK)
    c.setFont(font_name, 12)
    
    # Category
    cat_name = expense.category.name if expense.category else "N/A"
    c.drawRightString(width - 60, y - 20, arabic(f"التصنيف: {cat_name}"))
    
    # Description
    c.drawRightString(width - 60, y - 45, arabic(f"وذلك عن: {expense.description}"))

    # --- Footer ---
    footer_y = 50
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(50, footer_y + 30, width - 50, footer_y + 30)
    
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawCentredString(width / 2, footer_y + 10, arabic("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_ledger_report(entries, date_range_text=None):
    """
    Generates a multi-page PDF report for the General Ledger.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # Fonts - Use the same approach as other PDF functions
    font_name = 'Helvetica'  # Default
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
                font_name = 'Arabic'
                break
    except:
        pass

    # Branding Colors
    GOLD = HexColor('#C5A059')
    DARK = HexColor('#1F1F1F')
    GRAY = HexColor('#757575')
    LIGHT_GRAY = HexColor('#F9F9F9')

    def arabic(text):
        if font_name != 'Arabic': return text
        try:
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except:
            return text

    # Account name translations
    ACCOUNT_TRANSLATIONS = {
        'Accounts Receivable': 'ذمم مدينة',
        'Rental Income': 'إيرادات الإيجار',
        'Utility Income': 'إيرادات الخدمات',
        'Service Income': 'إيرادات الخدمات',
        'Bank / Cash': 'البنك / النقد',
        'Maintenance': 'صيانة',
        'Utilities': 'خدمات عامة',
        'Management': 'رسوم إدارة',
        'Cleaning': 'نظافة',
        'Tax': 'ضرائب',
        'Insurance': 'تأمين',
        'Other': 'أخرى',
    }
    
    def translate_account(account_name):
        """Translate account name to Arabic if available."""
        return ACCOUNT_TRANSLATIONS.get(account_name, account_name)

    def draw_header(c, page_num):
        # --- Header Band ---
        c.setFillColor(DARK) 
        c.rect(0, height - 140, width, 140, fill=1, stroke=0)
        
        c.setFillColor(GOLD)
        c.rect(0, height - 145, width, 5, fill=1, stroke=0)

        # Company Title (Right)
        c.setFillColor(GOLD)
        c.setFont(font_name, 32)
        c.drawRightString(width - 50, height - 70, arabic("أبـو رخيـة بـلازا"))
        
        c.setFillColor(colors.white)
        c.setFont(font_name, 14)
        c.drawRightString(width - 50, height - 100, arabic("إدارة العقارات والاستثمارات"))

        # Document Label (Left)
        c.setFillColor(colors.white)
        c.setFont(font_name, 24)
        c.drawString(50, height - 70, arabic("دفتر الأستاذ العام"))
        
        # Date Range / Page Info
        c.setFont(font_name, 11)
        c.setFillColor(colors.white)
        if date_range_text:
            c.drawString(50, height - 100, arabic(f"الفترة: {date_range_text}"))
        else:
            import datetime
            c.drawString(50, height - 100, arabic(f"تاريخ الطباعة: {datetime.date.today()}"))
        
        # Page number (bottom right of header)
        c.setFont(font_name, 10)
        c.setFillColor(GRAY)
        c.drawRightString(width - 50, height - 130, arabic(f"صفحة {page_num}"))

    def draw_table_header(c, y):
        c.setFillColor(LIGHT_GRAY)
        c.rect(30, y - 8, width - 60, 25, fill=1, stroke=0)
        
        c.setFillColor(DARK)
        c.setFont(font_name, 11)
        
        # Columns RTL: Date | Account | Description | Credit | Debit
        row_y = y 
        c.drawRightString(width - 40, row_y, arabic("التاريخ"))
        c.drawRightString(width - 120, row_y, arabic("الحساب"))
        c.drawRightString(width - 260, row_y, arabic("البيان / الوصف"))
        c.drawRightString(width - 460, row_y, arabic("دائن"))  # Credit now before Debit
        c.drawRightString(width - 520, row_y, arabic("مدين"))  # Debit now after Credit
        
        return y - 30

    # --- Start ---
    y = height - 200
    draw_header(c, 1)
    y = draw_table_header(c, y)

    total_debit = 0
    total_credit = 0

    c.setFont(font_name, 10)
    c.setFillColor(DARK)

    for entry in entries:
        if y < 60: # New Page
            c.showPage()
            y = height - 180
            draw_header(c, c.getPageNumber())
            y = draw_table_header(c, y)
            c.setFont(font_name, 10)
            c.setFillColor(DARK)

        # Data
        d_str = str(entry.transaction_date)
        acct = arabic(translate_account(entry.account_name))
        desc = arabic(entry.description[:50] + '...' if len(entry.description) > 50 else entry.description)
        dr = f"{entry.debit:,.2f}" if entry.debit > 0 else "-"
        cr = f"{entry.credit:,.2f}" if entry.credit > 0 else "-"

        c.drawRightString(width - 40, y, d_str)
        c.drawRightString(width - 120, y, acct)
        c.drawRightString(width - 260, y, desc)
        
        # Credit column (now before Debit in RTL order)
        if entry.credit > 0:
            c.setFillColor(colors.black)
            c.drawRightString(width - 460, y, cr)
        else:
            c.setFillColor(GRAY)
            c.drawRightString(width - 460, y, cr)
            
        # Debit column (now after Credit in RTL order)
        if entry.debit > 0: 
            c.setFillColor(colors.black)
            c.drawRightString(width - 520, y, dr)
        else:
            c.setFillColor(GRAY)
            c.drawRightString(width - 520, y, dr)
        
        c.setFillColor(DARK) # Reset text color
        
        # Gray separator line
        c.setStrokeColor(colors.Color(0.95, 0.95, 0.95))
        c.line(30, y - 8, width - 30, y - 8)

        y -= 25
        total_debit += entry.debit
        total_credit += entry.credit

    # Totals
    y -= 10
    if y < 60:
        c.showPage()
        y = height - 100
        
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(30, y + 10, width - 30, y + 10)
    
    c.setFont(font_name, 11)
    c.setFillColor(DARK)
    c.drawRightString(width - 260, y - 5, arabic("الإجمالي:"))
    c.drawRightString(width - 460, y - 5, f"{total_credit:,.2f}")  # Credit total
    c.drawRightString(width - 520, y - 5, f"{total_debit:,.2f}")   # Debit total

    # --- Footer ---
    footer_y = 50
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(50, footer_y + 30, width - 50, footer_y + 30)
    
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawCentredString(width / 2, footer_y + 10, arabic("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
