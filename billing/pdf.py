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
    # Always reshape/bidi, even if font fallback occurred.
    # This prevents 'reversed' text (logical order) on fallback fonts.
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
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
    
    def ar(t): return arabic_text(t, font_name)

    # --- Header ---
    # Top Gold Strip
    c.setFillColor(GOLD)
    c.rect(0, height - 12, width, 12, fill=1, stroke=0)

    # Logo
    logo_path = os.path.join(settings.MEDIA_ROOT, 'AbuRakhiaLogo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 100, width=110, height=80, preserveAspectRatio=True, mask='auto', anchor='sw')

    # Status Tag (Top Right)
    status_map = {
        'PAID': ('PAID / خالص', GREEN_SUCCESS),
        'PARTIALLY_PAID': ('PARTIAL / جزئي', GOLD),
        'ISSUED': ('UNPAID / غير مدفوعة', RED_ALERT),
        'DRAFT': ('DRAFT / مسودة', GRAY),
        'OVERDUE': ('OVERDUE / متأخرة', RED_ALERT)
    }
    st_text, st_color = status_map.get(invoice.status, (invoice.status, GRAY))
    
    c.setStrokeColor(st_color)
    c.setFillColor(st_color)
    c.setLineWidth(1)
    c.roundRect(width - 160, height - 60, 120, 30, 4, stroke=1, fill=0)
    c.setFont(font_name, 11)
    c.drawCentredString(width - 100, height - 50, ar(st_text))

    # Company Info (Left under logo)
    y_info = height - 110
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawString(45, y_info, "Abu Rakhieh Plaza - Amman")
    c.drawString(45, y_info - 12, "7th Circle, Abdullah Ghosheh St.")
    c.drawString(45, y_info - 24, "+962 77 50 000 95")

    # Title & Number (Right)
    c.setFillColor(DARK)
    c.setFont(font_name, 24)
    c.drawRightString(width - 40, height - 100, ar("فاتورة ضريبية"))
    c.setFont(font_name, 14)
    c.setFillColor(GOLD)
    c.drawRightString(width - 40, height - 120, f"TAX INVOICE #{invoice.invoice_number}")

    # Separator
    c.setStrokeColor(HexColor('#E0E0E0'))
    c.setLineWidth(1)
    c.line(40, height - 150, width - 40, height - 150)

    # --- Bill To & Details ---
    y = height - 190
    
    # Bill To
    c.setFillColor(GOLD)
    c.setFont(font_name, 9)
    c.drawString(40, y, "BILL TO / السيد")
    
    c.setFillColor(DARK)
    c.setFont(font_name, 12)
    # Tenant Name Logic
    tenant_name = invoice.tenant.name if invoice.tenant else "Cash Client"
    c.drawString(40, y - 20, ar(tenant_name))
    
    # Dates
    c.setFillColor(GOLD)
    c.setFont(font_name, 9)
    c.drawRightString(width - 40, y, "DATES / التواريخ")
    
    c.setFillColor(DARK)
    c.setFont(font_name, 10)
    c.drawRightString(width - 40, y - 18, f"Issue Date: {invoice.issue_date}")
    c.drawRightString(width - 40, y - 32, f"Due Date: {invoice.due_date}")

    # --- Table ---
    y = height - 260
    
    # Header
    c.setFillColor(LIGHT_GOLD)
    c.rect(40, y - 6, width - 80, 26, fill=1, stroke=0)
    
    c.setFillColor(DARK)
    c.setFont(font_name, 10)
    c.drawString(50, y + 2, ar("DESCRIPTION / البيان"))
    c.drawRightString(width - 50, y + 2, ar("AMOUNT / المبلغ"))
    
    # Row
    y -= 35
    c.setFillColor(DARK)
    c.setFont(font_name, 11)
    
    invoice_type_map = {
        'RENT': 'Rent Payment / دفعة إيجار',
        'UTILITY': 'Utilities / خدمات',
        'SERVICE': 'Service Fee / رسوم خدمات',
        'PENALTY': 'Penalty / غرامة'
    }
    desc_text = invoice_type_map.get(invoice.invoice_type, 'Service')
    if invoice.contract and invoice.contract.unit:
        desc_text += f" - Unit {invoice.contract.unit.unit_number}"
        
    c.drawString(50, y, ar(desc_text))
    c.drawRightString(width - 50, y, f"{invoice.total_amount:,.2f} JOD")
    
    c.setStrokeColor(HexColor('#F0F0F0'))
    c.line(40, y - 12, width - 40, y - 12)

    # --- Totals ---
    y -= 50
    c.setFillColor(DARK)
    c.setFont(font_name, 11)
    c.drawRightString(width - 150, y, "Total / المجموع")
    
    c.setFillColor(GOLD)
    c.setFont(font_name, 16)
    c.drawRightString(width - 50, y - 2, f"{invoice.total_amount:,.2f} JOD")

    # Paid Amount
    y -= 30
    c.setFillColor(GRAY)
    c.setFont(font_name, 10)
    c.drawRightString(width - 50, y, f"Paid: {invoice.paid_amount:,.2f}")
    
    # --- Footer ---
    footer_y = 40
    c.setStrokeColor(GOLD) 
    c.setLineWidth(1)
    c.line(40, footer_y + 30, width - 40, footer_y + 30)
    
    c.setFillColor(GRAY)
    c.setFont(font_name, 8)
    c.drawCentredString(width / 2, footer_y + 10, "Abu Rakhieh Plaza Property Management © 2026")
    
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

    # Contact Info
    y_info = height - 110
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    c.drawString(160, y_info, "Abu Rakhieh Plaza")
    c.drawString(160, y_info - 12, "Amman, 7th Circle")
    c.drawString(160, y_info - 24, "+962 77 50 000 95")

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

    # Contact Info
    y_info = height - 110
    c.setFillColor(GRAY)
    c.setFont(font_name, 9)
    # Align with receipt style (indented from logo)
    c.drawString(160, y_info, "Abu Rakhieh Plaza")
    c.drawString(160, y_info - 12, "Amman, 7th Circle")
    c.drawString(160, y_info - 24, "+962 77 50 000 95")

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
    # Combine description and building info if relevant
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
