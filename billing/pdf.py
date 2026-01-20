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

# --- Global Config ---
A4_WIDTH, A4_HEIGHT = A4

def register_fonts():
    """Helper to register fonts. Enforces bundled font for production consistency."""
    font_name = 'Helvetica'
    try:
        # Try multiple strategies to find the font asset
        possible_paths = []
        
        # 1. Django BASE_DIR (Standard)
        possible_paths.append(os.path.join(settings.BASE_DIR, 'assets', 'fonts', 'Amiri-Regular.ttf'))
        
        # 2. Relative to this file (Reliable independent of CWD/Settings)
        # file is in backend/billing/pdf.py
        # assets is in backend/assets/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        possible_paths.append(os.path.join(backend_dir, 'assets', 'fonts', 'Amiri-Regular.ttf'))
        
        # 3. CWD fallback
        possible_paths.append(os.path.join(os.getcwd(), 'assets', 'fonts', 'Amiri-Regular.ttf'))
        
        font_path = None
        for path in possible_paths:
            if os.path.exists(path):
                font_path = path
                break
        
        if font_path:
            pdfmetrics.registerFont(TTFont('Arabic', font_path))
            return 'Arabic'
        else:
            print(f"WARNING: Bundled font not found. Searched: {possible_paths}")
            
    except Exception as e:
        print(f"Font registration error: {e}")
        
    return font_name

def arabic_text(text, font_name):
    """Reshapes Arabic text for PDF."""
    try:
        # 1. Reshape characters (connect letters)
        reshaped = arabic_reshaper.reshape(text)
        # 2. Reorder for RTL display (Bidi)
        # Note: ReportLab draws strings LTR by default. 
        # get_display reverses it to visual order which ReportLab renders "correctly" from right to left if we draw it that way?
        # Actually, get_display makes it so if you print it LTR, it looks RTL.
        bidi_text = get_display(reshaped)
        return bidi_text
    except:
        return text

# --- Theme Colors ---
GOLD = HexColor('#C5A059')
DARK = HexColor('#1A1A1A')
GRAY = HexColor('#666666')
LIGHT_GOLD = HexColor('#FEFDF5')
LIGHT_GRAY = HexColor('#F9F9F9')
RED_ALERT = HexColor('#C62828')
GREEN_SUCCESS = HexColor('#2E7D32')

def generate_invoice_pdf(invoice):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = register_fonts()
    
    def ar(t): 
        """Properly handle Arabic text rendering"""
        if not t:
            return ""
        text_str = str(t)
        # Only apply reshaping to text that contains Arabic characters
        if any('\u0600' <= char <= '\u06FF' for char in text_str):
            return arabic_text(text_str, font_name)
        return text_str

    # Brand Color Palette - Gold and White Theme
    GOLD_DARK = HexColor('#8B7355')   # Darker gold for text
    GOLD_MEDIUM = HexColor('#A0826D') # Medium gold for secondary text
    GOLD_LIGHT = HexColor('#D4C5B9')  # Light gold for subtle elements
    
    # --- Header Section ---
    # Gold Top Bar
    c.setFillColor(GOLD)
    c.rect(0, height - 20, width, 20, fill=1, stroke=0)

    # Logo
    logo_path = os.path.join(settings.MEDIA_ROOT, 'AbuRakhiaLogo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 120, width=130, height=95, preserveAspectRatio=True, mask='auto', anchor='sw')

    # Invoice Title (Right Side)
    c.setFillColor(GOLD_DARK)
    c.setFont(font_name, 28)
    c.drawRightString(width - 40, height - 70, ar("فاتورة"))
    
    c.setFont(font_name, 11)
    c.setFillColor(GOLD_MEDIUM)
    c.drawRightString(width - 40, height - 90, "INVOICE")

    # Invoice Number
    c.setFillColor(GOLD)
    c.setFont(font_name, 14)
    c.drawRightString(width - 40, height - 115, f"#{invoice.invoice_number}")

    # Status Badge
    status_map = {
        'PAID': ('مدفوعة', GREEN_SUCCESS),
        'PARTIALLY_PAID': ('مدفوعة جزئياً', GOLD),
        'ISSUED': ('صادرة', GOLD),
        'DRAFT': ('مسودة', GOLD_MEDIUM),
        'OVERDUE': ('متأخرة', RED_ALERT)
    }
    status_text, status_color = status_map.get(invoice.status, (invoice.status, GOLD_MEDIUM))
    
    c.setFillColor(status_color)
    c.roundRect(width - 140, height - 145, 100, 22, 3, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont(font_name, 9)
    c.drawCentredString(width - 90, height - 137, ar(status_text))

    # Divider
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(1)
    c.line(40, height - 165, width - 40, height - 165)

    # --- Information Grid ---
    y_info = height - 200
    
    # Right Column: Invoice Details
    c.setFillColor(GOLD)
    c.setFont(font_name, 8)
    c.drawRightString(width - 40, y_info, ar("تفاصيل الفاتورة"))
    
    y_info -= 18
    
    # Helper for right-aligned info rows
    def draw_right_info(y, label_ar, value):
        c.setFillColor(GOLD_MEDIUM)
        c.setFont(font_name, 9)
        c.drawRightString(width - 40, y, ar(label_ar))
        
        c.setFillColor(GOLD_DARK)
        c.setFont(font_name, 10)
        c.drawRightString(width - 130, y, str(value))
        return y - 16
    
    y_info = draw_right_info(y_info, "تاريخ الإصدار:", invoice.issue_date)
    y_info = draw_right_info(y_info, "تاريخ الاستحقاق:", invoice.due_date)
    y_info = draw_right_info(y_info, "نوع الفاتورة:", ar(invoice.invoice_type))

    # Left Column: Bill To (WITHOUT PHONE)
    y_bill = height - 200
    c.setFillColor(GOLD)
    c.setFont(font_name, 8)
    c.drawString(40, y_bill, ar("الفاتورة إلى"))
    
    y_bill -= 18
    c.setFillColor(GOLD_DARK)
    c.setFont(font_name, 11)
    tenant_name = invoice.tenant.name if invoice.tenant else "عميل نقدي"
    c.drawString(40, y_bill, ar(tenant_name))
    
    # REMOVED: Phone number display to avoid reversed text issue

    # --- Items Table ---
    y_table = height - 300
    
    # Table Header (Gold theme)
    c.setFillColor(GOLD)
    c.rect(40, y_table - 5, width - 80, 28, fill=1, stroke=0)
    
    c.setFillColor(colors.white)
    c.setFont(font_name, 10)
    # RTL: Description on right, Amount on left
    c.drawRightString(width - 60, y_table + 5, ar("البيان"))
    c.drawString(60, y_table + 5, ar("المبلغ"))
    
    # Table Row
    y_row = y_table - 25
    c.setFillColor(GOLD_DARK)
    c.setFont(font_name, 11)
    
    # Build description
    desc_parts = []
    if invoice.description:
        desc_parts.append(invoice.description)
    
    if invoice.contract and invoice.contract.unit:
        desc_parts.append(f"الوحدة {invoice.contract.unit.unit_number}")
    
    # Draw description (right-aligned)
    desc_y = y_row
    for part in desc_parts:
        c.drawRightString(width - 60, desc_y, ar(part))
        desc_y -= 16
    
    # Draw amount (left-aligned) - Fixed positioning
    c.setFont(font_name, 12)
    c.setFillColor(GOLD_DARK)
    c.drawString(60, y_row, f"{invoice.total_amount:,.2f}")
    c.setFont(font_name, 9)
    c.setFillColor(GOLD_MEDIUM)
    # Position JOD after the number with proper spacing
    amount_width = c.stringWidth(f"{invoice.total_amount:,.2f}", font_name, 12)
    c.drawString(60 + amount_width + 5, y_row, "JOD")
    
    # Bottom border
    final_row_y = min(desc_y, y_row - 20)
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(0.5)
    c.line(40, final_row_y - 10, width - 40, final_row_y - 10)

    # --- Totals Section (Right-Aligned) ---
    y_totals = final_row_y - 50
    
    # Create a totals box on the right
    box_x = width - 250
    box_width = 210
    
    # Background - Light gold tint
    c.setFillColor(HexColor('#FBF8F3'))
    c.roundRect(box_x, y_totals - 80, box_width, 90, 5, stroke=0, fill=1)
    
    # Border - Gold
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(1)
    c.roundRect(box_x, y_totals - 80, box_width, 90, 5, stroke=1, fill=0)
    
    y_total_line = y_totals - 15
    
    def draw_total_line(y, label, amount, is_main=False, is_alert=False):
        # Label
        label_color = GOLD_MEDIUM if not is_main and not is_alert else GOLD_DARK if is_main else RED_ALERT
        c.setFillColor(label_color)
        c.setFont(font_name, 10 if not is_main else 12)
        c.drawRightString(width - 60, y, ar(label))
        
        # Amount and JOD positioning
        amount_color = GOLD if is_main else RED_ALERT if is_alert else GOLD_DARK
        c.setFillColor(amount_color)
        amount_font_size = 14 if is_main else 11
        c.setFont(font_name, amount_font_size)
        
        # Draw amount
        amount_str = f"{amount:,.2f}"
        amount_x = width - 100  # Position for amount
        c.drawRightString(amount_x, y, amount_str)
        
        # JOD - positioned to the RIGHT of the amount (after it)
        c.setFont(font_name, 8)
        c.setFillColor(GOLD_MEDIUM)
        # Position JOD slightly to the right of where amount ends
        jod_x = amount_x + 5
        c.drawString(jod_x, y - 1, "JOD")
        
        return y - 22
    
    y_total_line = draw_total_line(y_total_line, "المجموع:", invoice.total_amount, is_main=True)
    
    # Divider
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(0.5)
    c.line(box_x + 10, y_total_line + 8, box_x + box_width - 10, y_total_line + 8)
    
    y_total_line = draw_total_line(y_total_line, "المدفوع:", invoice.paid_amount)
    
    balance = invoice.total_amount - invoice.paid_amount
    if balance > 0:
        y_total_line = draw_total_line(y_total_line, "المتبقي:", balance, is_alert=True)

    # --- Footer ---
    footer_y = 50
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(40, footer_y + 25, width - 40, footer_y + 25)
    
    c.setFillColor(GOLD_MEDIUM)
    c.setFont(font_name, 8)
    c.drawCentredString(width / 2, footer_y + 10, ar("أبو رخية بلازا - إدارة العقارات"))
    c.drawCentredString(width / 2, footer_y, ar("عمان، الدوار السابع، شارع عبدالله غوشة"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_receipt_pdf(payment):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = register_fonts()
    
    def ar(t): return arabic_text(t, font_name)

    # --- Top Bar ---
    c.setFillColor(GOLD)
    c.rect(0, height - 12, width, 12, fill=1, stroke=0)

    # --- Header ---
    logo_path = os.path.join(settings.MEDIA_ROOT, 'AbuRakhiaLogo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 100, width=110, height=80, preserveAspectRatio=True, mask='auto', anchor='sw')

    # Title
    c.setFillColor(DARK)
    c.setFont(font_name, 26)
    c.drawRightString(width - 40, height - 70, ar("سـنـد قـبـض"))
    c.setFont(font_name, 11)
    c.setFillColor(GOLD)
    c.drawRightString(width - 40, height - 90, "RECEIPT VOUCHER")

    # Receipt Number
    c.setFillColor(DARK)
    c.setFont(font_name, 16)
    c.drawRightString(width - 40, height - 115, f"Ref. {payment.reference_number}")

    # Separator
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(40, height - 140, width - 40, height - 140)

    # Contact Info WITHOUT PHONE
    y_info = height - 110
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawString(160, y_info, "Abu Rakhieh Plaza")
    c.drawString(160, y_info - 12, "Amman, 7th Circle")
    # c.drawString(160, y_info - 24, "+962 77 50 000 95") # REMOVED

    # --- Body Fields ---
    y = height - 190
    gap = 48 

    def draw_field(title_en, title_ar, value, y_pos):
        # Label
        c.setFillColor(GOLD)
        c.setFont(font_name, 9)
        c.drawString(40, y_pos + 12, title_en.upper())
        c.drawRightString(width - 40, y_pos + 12, ar(title_ar))
        
        # Value
        c.setFillColor(DARK)
        c.setFont(font_name, 13)
        val_str = str(value) if value else "-"
        c.drawCentredString(width / 2, y_pos, ar(val_str))
        
        # Underline
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.setLineWidth(0.5)
        c.line(40, y_pos - 8, width - 40, y_pos - 8)
        
        return y_pos - gap

    # 1. Date
    y = draw_field("Transaction Date", "التاريخ", str(payment.payment_date), y)

    # 2. Received From
    client_name = "Cash Client"
    if payment.invoice and payment.invoice.tenant:
        client_name = payment.invoice.tenant.name
    y = draw_field("Received From", "وصلنا من السادة", client_name, y)

    # 3. Sum
    y = draw_field("The Sum of", "مبلغ وقدره", f"{payment.amount:,.2f} JOD", y)

    # 4. Description (As Payment Of)
    desc = payment.payment_for
    if not desc:
         desc = f"Payment for Invoice #{payment.invoice.invoice_number}"
    y = draw_field("As Payment Of", "وذلك عن", desc, y)

    # 5. Method
    method_str = payment.get_payment_method_display()
    detail_str = method_str
    if payment.payment_method == 'CHECK':
         cheque_ref = payment.reference_number or "N/A"
         bank_name = "Unknown"
         if payment.cheques.exists():
             bank_name = payment.cheques.first().bank_name
         detail_str = f"Cheque #{cheque_ref} - {bank_name}"
    elif payment.payment_method == 'TRANSFER':
         ref = payment.reference_number or ""
         detail_str = f"Bank Transfer {ref}"
    
    method_map_ar = {'CASH': 'نقد', 'CHECK': 'شيك', 'TRANSFER': 'تحويل', 'POS': 'شبكة'}
    ar_method = method_map_ar.get(payment.payment_method, "")
    
    if payment.payment_method == 'CASH':
        final_detail = ar("نقد")
    else:
        final_detail = f"{detail_str} / {ar(ar_method)}"
    
    y = draw_field("Payment Method", "طريقة الدفع", final_detail, y)
    
    # 6. Notes
    if payment.notes:
        c.setFillColor(GRAY)
        c.setFont(font_name, 10)
        c.drawString(40, y, f"Note: {payment.notes}")
        y -= 30

    # --- Signature ---
    sig_y = 80
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.rect(width - 200, sig_y, 160, 50, stroke=1, fill=0)
    c.setFillColor(GOLD)
    c.setFont(font_name, 9)
    c.drawCentredString(width - 120, sig_y - 12, f"Authorized Signature / {ar('التوقيع')}")

    # --- Footer ---
    footer_y = 30
    c.setFillColor(DARK)
    c.setFont(font_name, 8)
    c.drawCentredString(width / 2, footer_y, "Abu Rakhieh Plaza Property Management")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_expense_pdf(expense):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = register_fonts()
    
    def ar(t): return arabic_text(t, font_name)

    # --- Top Bar ---
    c.setFillColor(GOLD)
    c.rect(0, height - 12, width, 12, fill=1, stroke=0)

    # --- Header ---
    logo_path = os.path.join(settings.MEDIA_ROOT, 'AbuRakhiaLogo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 100, width=110, height=80, preserveAspectRatio=True, mask='auto', anchor='sw')

    # Title
    c.setFillColor(DARK)
    c.setFont(font_name, 26)
    c.drawRightString(width - 40, height - 70, ar("سـنـد صـرف"))
    c.setFont(font_name, 11)
    c.setFillColor(GOLD)
    c.drawRightString(width - 40, height - 90, "EXPENSE VOUCHER")

    # Reference Number
    ref_text = expense.invoice_reference if expense.invoice_reference else str(expense.id)
    c.setFillColor(DARK)
    c.setFont(font_name, 16)
    c.drawRightString(width - 40, height - 115, f"Ref. {ref_text}")

    # Separator
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(40, height - 140, width - 40, height - 140)

    # Contact Info WITHOUT PHONE
    y_info = height - 110
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    # Align with receipt style (indented from logo)
    c.drawString(160, y_info, "Abu Rakhieh Plaza")
    c.drawString(160, y_info - 12, "Amman, 7th Circle")
    # c.drawString(160, y_info - 24, "+962 77 50 000 95")

    # --- Body Fields ---
    y = height - 190
    gap = 48 

    def draw_field(title_en, title_ar, value, y_pos):
        # Label
        c.setFillColor(GOLD)
        c.setFont(font_name, 9)
        c.drawString(40, y_pos + 12, title_en.upper())
        c.drawRightString(width - 40, y_pos + 12, ar(title_ar))
        
        # Value
        c.setFillColor(DARK)
        c.setFont(font_name, 13)
        val_str = str(value) if value else "-"
        c.drawCentredString(width / 2, y_pos, ar(val_str))
        
        # Underline
        c.setStrokeColor(HexColor('#DDDDDD'))
        c.setLineWidth(0.5)
        c.line(40, y_pos - 8, width - 40, y_pos - 8)
        
        return y_pos - gap

    # 1. Date
    y = draw_field("Transaction Date", "التاريخ", str(expense.expense_date), y)

    # 2. Paid To (Vendor)
    payee = expense.vendor_name if expense.vendor_name else "Petty Cash / نثريات"
    y = draw_field("Paid To", "صرفنا إلى السيد/السادة", payee, y)

    # 3. Sum
    y = draw_field("The Sum of", "مبلغ وقدره", f"{expense.amount:,.2f} JOD", y)

    # 4. Category
    cat_name = expense.category.name if expense.category else "General"
    y = draw_field("Category", "التصنيف", cat_name, y)

    # 5. Description (For)
    # Use explicit expense_for if available (Dynamic like payments)
    desc = expense.expense_for
    if not desc:
        # Fallback to standard description + location
        desc = expense.description
        if expense.unit:
            desc += f" - Unit {expense.unit.unit_number}"
        elif expense.building:
            desc += f" - {expense.building.name}"
        
    y = draw_field("Description", "وذلك عن", desc, y)

    # --- Signature ---
    sig_y = 80
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.rect(width - 200, sig_y, 160, 50, stroke=1, fill=0)
    c.setFillColor(GOLD)
    c.setFont(font_name, 9)
    c.drawCentredString(width - 120, sig_y - 12, f"Authorized Signature / {ar('التوقيع')}")

    # --- Footer ---
    footer_y = 30
    c.setFillColor(DARK)
    c.setFont(font_name, 8)
    c.drawCentredString(width / 2, footer_y, "Abu Rakhieh Plaza Property Management")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def generate_ledger_report(entries, date_range_text=None):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = register_fonts()
    def ar(t): return arabic_text(t, font_name)

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
        return ACCOUNT_TRANSLATIONS.get(account_name, account_name)

    def draw_header(c, page_num):
        c.setFillColor(DARK) 
        c.rect(0, height - 140, width, 140, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.rect(0, height - 145, width, 5, fill=1, stroke=0)

        c.setFillColor(GOLD)
        c.setFont(font_name, 32)
        c.drawRightString(width - 50, height - 70, ar("أبـو رخيـة بـلازا"))
        
        c.setFillColor(colors.white)
        c.setFont(font_name, 14)
        c.drawRightString(width - 50, height - 100, ar("إدارة العقارات والاستثمارات"))

        c.setFillColor(colors.white)
        c.setFont(font_name, 24)
        c.drawString(50, height - 70, ar("دفتر الأستاذ العام"))
        
        c.setFont(font_name, 11)
        c.setFillColor(colors.white)
        if date_range_text:
            c.drawString(50, height - 100, ar(f"الفترة: {date_range_text}"))
        else:
            import datetime
            c.drawString(50, height - 100, ar(f"تاريخ الطباعة: {datetime.date.today()}"))
        
        c.setFont(font_name, 10)
        c.setFillColor(GRAY)
        c.drawRightString(width - 50, height - 130, ar(f"صفحة {page_num}"))

    def draw_table_header(c, y):
        c.setFillColor(LIGHT_GRAY)
        c.rect(30, y - 8, width - 60, 25, fill=1, stroke=0)
        c.setFillColor(DARK)
        c.setFont(font_name, 11)
        row_y = y 
        c.drawRightString(width - 40, row_y, ar("التاريخ"))
        c.drawRightString(width - 120, row_y, ar("الحساب"))
        c.drawRightString(width - 260, row_y, ar("البيان / الوصف"))
        c.drawRightString(width - 460, row_y, ar("دائن"))
        c.drawRightString(width - 520, row_y, ar("مدين"))
        return y - 30

    y = height - 200
    draw_header(c, 1)
    y = draw_table_header(c, y)

    total_debit = 0
    total_credit = 0

    c.setFont(font_name, 10)
    c.setFillColor(DARK)

    for entry in entries:
        if y < 60:
            c.showPage()
            y = height - 180
            draw_header(c, c.getPageNumber())
            y = draw_table_header(c, y)
            c.setFont(font_name, 10)
            c.setFillColor(DARK)

        d_str = str(entry.transaction_date)
        acct = ar(translate_account(entry.account_name))
        desc = ar(entry.description[:50] + '...' if len(entry.description) > 50 else entry.description)
        dr = f"{entry.debit:,.2f}" if entry.debit > 0 else "-"
        cr = f"{entry.credit:,.2f}" if entry.credit > 0 else "-"

        c.drawRightString(width - 40, y, d_str)
        c.drawRightString(width - 120, y, acct)
        c.drawRightString(width - 260, y, desc)
        
        if entry.credit > 0:
            c.setFillColor(colors.black)
            c.drawRightString(width - 460, y, cr)
        else:
            c.setFillColor(GRAY)
            c.drawRightString(width - 460, y, cr)
            
        if entry.debit > 0: 
            c.setFillColor(colors.black)
            c.drawRightString(width - 520, y, dr)
        else:
            c.setFillColor(GRAY)
            c.drawRightString(width - 520, y, dr)
        
        c.setFillColor(DARK)
        c.setStrokeColor(colors.Color(0.95, 0.95, 0.95))
        c.line(30, y - 8, width - 30, y - 8)

        y -= 25
        total_debit += entry.debit
        total_credit += entry.credit

    y -= 10
    if y < 60:
        c.showPage()
        y = height - 100
        
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(30, y + 10, width - 30, y + 10)
    
    c.setFont(font_name, 11)
    c.setFillColor(DARK)
    c.drawRightString(width - 260, y - 5, ar("الإجمالي:"))
    c.drawRightString(width - 460, y - 5, f"{total_credit:,.2f}")
    c.drawRightString(width - 520, y - 5, f"{total_debit:,.2f}")

    # Footer
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(50, 80, width - 50, 80)
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawCentredString(width / 2, 60, ar("أبو رخية بلازا - جميع الحقوق محفوظة © 2026"))

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
