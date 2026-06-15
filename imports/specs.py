"""
Smart import engine for Invoices, Expenses and Payments.

The frontend parses any spreadsheet (xlsx/xls/csv) into rows of {field: value}
after the user maps columns. This module:

  * exposes a field SPEC per resource (labels EN/AR + synonyms for auto-mapping),
  * validates rows (smart parsing of dates/numbers, reference resolution),
  * commits valid rows by reusing the existing, tested service layer so that
    ledger postings and invoice balances stay correct.

Everything stays building-isolated: the target building is validated against the
user's access and every created record is scoped to it.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from users.building_access import (
    user_can_access_building, scope_tenants, scope_units, scope_invoices,
)

# ---------------------------------------------------------------------------
# Smart value parsing
# ---------------------------------------------------------------------------

_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

_DATE_FORMATS = [
    '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y',
    '%d.%m.%Y', '%Y.%m.%d', '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y',
    '%d/%m/%y', '%m/%d/%y',
]


def clean_str(v) -> str:
    if v is None:
        return ''
    return str(v).strip()


def parse_decimal(v):
    """Parse money-ish text: handles currency symbols, thousands separators,
    Arabic digits and decimal commas."""
    s = clean_str(v).translate(_ARABIC_DIGITS)
    if not s:
        return None
    s = re.sub(r'[^\d.,\-]', '', s)
    if not s or s in ('-', '.', ','):
        return None
    if ',' in s and '.' in s:
        # Whichever comes last is the decimal separator.
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        parts = s.split(',')
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = s.replace(',', '.')          # decimal comma
        else:
            s = s.replace(',', '')           # thousands
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def parse_date(v):
    """Parse common date strings and Excel serial numbers."""
    if isinstance(v, (datetime, date)):
        return v.date() if isinstance(v, datetime) else v
    s = clean_str(v).translate(_ARABIC_DIGITS)
    if not s:
        return None
    # ISO with time component
    if 'T' in s:
        s = s.split('T', 1)[0]
    elif ' ' in s and ':' in s:
        s = s.split(' ', 1)[0]
    # Excel serial date (days since 1899-12-30)
    if re.fullmatch(r'\d{5}(\.\d+)?', s):
        try:
            return date(1899, 12, 30) + timedelta(days=int(float(s)))
        except (ValueError, OverflowError):
            pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


_PAYMENT_METHODS = {
    'TRANSFER': ['transfer', 'bank transfer', 'bank', 'wire', 'حوالة', 'تحويل', 'تحويل بنكي'],
    'CASH': ['cash', 'نقد', 'كاش', 'نقدا', 'نقدي', 'نقدية'],
    'CHECK': ['check', 'cheque', 'chk', 'شيك', 'شيكات', 'صك'],
    'POS': ['pos', 'point of sale', 'card', 'visa', 'mastercard', 'نقطة بيع', 'بطاقة', 'فيزا'],
}


def resolve_method(v):
    s = clean_str(v).lower().translate(_ARABIC_DIGITS)
    if not s:
        return None
    if s.upper() in _PAYMENT_METHODS:
        return s.upper()
    for code, names in _PAYMENT_METHODS.items():
        if any(s == n or n in s for n in names):
            return code
    return None


# ---------------------------------------------------------------------------
# Reference resolvers
# ---------------------------------------------------------------------------

def _resolve_tenant(user, building_id, val):
    from tenants.models import Tenant
    qs = scope_tenants(Tenant.objects.all(), user)
    v = clean_str(val)
    if not v:
        return []
    if v.isdigit():
        t = qs.filter(pk=int(v)).first()
        if t:
            return [t]
    matches = list(qs.filter(name__iexact=v))
    if not matches:
        matches = list(qs.filter(name__icontains=v))
    if len(matches) > 1 and building_id:
        narrowed = [m for m in matches if m.building_id == int(building_id)]
        if narrowed:
            matches = narrowed
    return matches


def _resolve_unit(user, building_id, val):
    from properties.models import Unit
    v = clean_str(val)
    if not v:
        return None
    qs = scope_units(Unit.objects.all(), user)
    if building_id:
        qs = qs.filter(floor__building_id=int(building_id))
    return qs.filter(unit_number__iexact=v).first()


def _resolve_invoice(user, val):
    from billing.models import Invoice
    v = clean_str(val)
    if not v:
        return None
    qs = scope_invoices(Invoice.objects.all(), user)
    inv = qs.filter(invoice_number__iexact=v).first()
    if not inv and v.isdigit():
        inv = qs.filter(pk=int(v)).first()
    return inv


# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------

class BaseHandler:
    key = ''
    label = ''
    label_ar = ''
    building_required = True
    fields = []  # list of dicts

    def meta(self):
        return {
            'key': self.key,
            'label': self.label,
            'label_ar': self.label_ar,
            'building_required': self.building_required,
            'fields': self.fields,
        }

    def resolve(self, row, *, user, building, building_id):
        """Return (clean: dict|None, errors: dict, display: dict)."""
        raise NotImplementedError

    def create(self, clean, *, user, building, building_id):
        """Persist a resolved row. Returns a short label for the created record."""
        raise NotImplementedError


class ExpenseHandler(BaseHandler):
    key = 'expenses'
    label = 'Expenses'
    label_ar = 'المصروفات'
    fields = [
        {'key': 'expense_date', 'label': 'Date', 'label_ar': 'التاريخ', 'type': 'date', 'required': True,
         'synonyms': ['date', 'expense date', 'transaction date', 'تاريخ', 'التاريخ', 'تاريخ المصروف']},
        {'key': 'description', 'label': 'Description', 'label_ar': 'البيان', 'type': 'text', 'required': True,
         'synonyms': ['description', 'desc', 'details', 'statement', 'item', 'البيان', 'الوصف', 'التفاصيل', 'البند']},
        {'key': 'amount', 'label': 'Amount', 'label_ar': 'المبلغ', 'type': 'number', 'required': True,
         'synonyms': ['amount', 'value', 'cost', 'total', 'price', 'المبلغ', 'القيمة', 'الإجمالي', 'التكلفة']},
        {'key': 'category', 'label': 'Category', 'label_ar': 'الفئة', 'type': 'text', 'required': False,
         'synonyms': ['category', 'type', 'expense category', 'الفئة', 'التصنيف', 'النوع', 'فئة المصروف'],
         'hint': 'Created automatically if it does not exist.'},
        {'key': 'vendor_name', 'label': 'Vendor', 'label_ar': 'المورد', 'type': 'text', 'required': False,
         'synonyms': ['vendor', 'supplier', 'payee', 'vendor name', 'المورد', 'اسم المورد', 'الجهة', 'المزود']},
        {'key': 'unit', 'label': 'Unit', 'label_ar': 'الوحدة', 'type': 'text', 'required': False,
         'synonyms': ['unit', 'unit number', 'apartment', 'shop', 'الوحدة', 'رقم الوحدة', 'المحل', 'الشقة']},
        {'key': 'invoice_reference', 'label': 'Reference', 'label_ar': 'المرجع', 'type': 'text', 'required': False,
         'synonyms': ['invoice reference', 'invoice number', 'ref', 'reference', 'bill number', 'رقم الفاتورة', 'المرجع']},
    ]

    def resolve(self, row, *, user, building, building_id):
        errors, display, clean = {}, {}, {}

        d = parse_date(row.get('expense_date'))
        if not d:
            errors['expense_date'] = 'Invalid or missing date'
        else:
            clean['expense_date'] = d
            display['expense_date'] = d.isoformat()

        desc = clean_str(row.get('description'))
        if not desc:
            errors['description'] = 'Required'
        else:
            clean['description'] = desc[:255]
            display['description'] = clean['description']

        amt = parse_decimal(row.get('amount'))
        if amt is None or amt <= 0:
            errors['amount'] = 'Invalid amount'
        else:
            clean['amount'] = amt
            display['amount'] = str(amt)

        cat_name = clean_str(row.get('category')) or 'General'
        clean['_category_name'] = cat_name[:100]
        display['category'] = clean['_category_name']

        clean['vendor_name'] = clean_str(row.get('vendor_name'))[:255]
        display['vendor_name'] = clean['vendor_name']

        unit_val = clean_str(row.get('unit'))
        if unit_val:
            unit = _resolve_unit(user, building_id, unit_val)
            if not unit:
                errors['unit'] = f"Unit '{unit_val}' not found in this building"
            else:
                clean['unit'] = unit
                display['unit'] = unit.unit_number
        else:
            clean['unit'] = None

        clean['invoice_reference'] = clean_str(row.get('invoice_reference'))[:100]

        if errors:
            return None, errors, display
        return clean, errors, display

    def create(self, clean, *, user, building, building_id):
        from expenses.models import Expense, ExpenseCategory
        from expenses.services import ExpenseService
        category, _ = ExpenseCategory.objects.get_or_create(
            building=building, name=clean['_category_name'],
        )
        expense = ExpenseService.record_expense({
            'building': building,
            'unit': clean.get('unit'),
            'category': category,
            'cost_type': Expense.CostType.DYNAMIC,
            'description': clean['description'],
            'vendor_name': clean.get('vendor_name', ''),
            'expense_for': '',
            'amount': clean['amount'],
            'expense_date': clean['expense_date'],
            'invoice_reference': clean.get('invoice_reference', ''),
        })
        return f"Expense #{expense.id}"


class PaymentHandler(BaseHandler):
    key = 'payments'
    label = 'Payments'
    label_ar = 'المدفوعات'
    building_required = False
    fields = [
        {'key': 'invoice_number', 'label': 'Invoice #', 'label_ar': 'رقم الفاتورة', 'type': 'text', 'required': True,
         'synonyms': ['invoice', 'invoice number', 'invoice no', 'inv', 'bill', 'رقم الفاتورة', 'الفاتورة', 'فاتورة']},
        {'key': 'amount', 'label': 'Amount', 'label_ar': 'المبلغ', 'type': 'number', 'required': True,
         'synonyms': ['amount', 'paid', 'payment', 'value', 'المبلغ', 'المدفوع', 'القيمة', 'الدفعة']},
        {'key': 'payment_date', 'label': 'Date', 'label_ar': 'التاريخ', 'type': 'date', 'required': True,
         'synonyms': ['date', 'payment date', 'paid date', 'تاريخ', 'تاريخ الدفع', 'التاريخ', 'تاريخ السداد']},
        {'key': 'payment_method', 'label': 'Method', 'label_ar': 'طريقة الدفع', 'type': 'choice', 'required': True,
         'synonyms': ['method', 'payment method', 'mode', 'type', 'طريقة الدفع', 'الطريقة', 'نوع الدفع'],
         'choices': [
             {'value': 'CASH', 'label': 'Cash'}, {'value': 'TRANSFER', 'label': 'Bank Transfer'},
             {'value': 'CHECK', 'label': 'Check'}, {'value': 'POS', 'label': 'Point of Sale'},
         ]},
        {'key': 'reference_number', 'label': 'Reference', 'label_ar': 'المرجع', 'type': 'text', 'required': False,
         'synonyms': ['reference', 'reference number', 'transaction id', 'check number', 'cheque number', 'المرجع', 'رقم المرجع', 'رقم الشيك']},
        {'key': 'paid_by', 'label': 'Paid by', 'label_ar': 'الدافع', 'type': 'text', 'required': False,
         'synonyms': ['paid by', 'payer', 'received from', 'الدافع', 'المدفوع بواسطة', 'استلمت من']},
        {'key': 'notes', 'label': 'Notes', 'label_ar': 'ملاحظات', 'type': 'text', 'required': False,
         'synonyms': ['notes', 'note', 'comment', 'remarks', 'ملاحظات', 'ملاحظة']},
    ]

    def resolve(self, row, *, user, building, building_id):
        errors, display, clean = {}, {}, {}

        inv_val = clean_str(row.get('invoice_number'))
        invoice = _resolve_invoice(user, inv_val) if inv_val else None
        if not inv_val:
            errors['invoice_number'] = 'Required'
        elif not invoice:
            errors['invoice_number'] = f"Invoice '{inv_val}' not found"
        else:
            clean['invoice'] = invoice
            display['invoice_number'] = invoice.invoice_number
            display['tenant'] = invoice.tenant.name

        d = parse_date(row.get('payment_date'))
        if not d:
            errors['payment_date'] = 'Invalid or missing date'
        else:
            clean['payment_date'] = d
            display['payment_date'] = d.isoformat()

        amt = parse_decimal(row.get('amount'))
        if amt is None or amt <= 0:
            errors['amount'] = 'Invalid amount'
        else:
            clean['amount'] = amt
            display['amount'] = str(amt)
            if invoice is not None:
                if invoice.status == 'PAID':
                    errors['amount'] = 'Invoice is already fully paid'
                elif amt > invoice.balance_due:
                    errors['amount'] = f'Exceeds balance due ({invoice.balance_due})'

        method = resolve_method(row.get('payment_method'))
        if not method:
            errors['payment_method'] = 'Unknown payment method'
        else:
            clean['payment_method'] = method
            display['payment_method'] = method

        clean['reference_number'] = clean_str(row.get('reference_number'))[:100]
        clean['paid_by'] = clean_str(row.get('paid_by'))[:200]
        clean['notes'] = clean_str(row.get('notes'))

        if errors:
            return None, errors, display
        return clean, errors, display

    def create(self, clean, *, user, building, building_id):
        from billing.services import BillingService
        payment = BillingService.receive_payment({
            'invoice': clean['invoice'],
            'amount': clean['amount'],
            'payment_date': clean['payment_date'],
            'payment_method': clean['payment_method'],
            'reference_number': clean.get('reference_number', ''),
            'paid_by': clean.get('paid_by', ''),
            'notes': clean.get('notes', ''),
        })
        return f"Payment #{payment.id}"


class InvoiceHandler(BaseHandler):
    key = 'invoices'
    label = 'Invoices'
    label_ar = 'الفواتير'
    fields = [
        {'key': 'tenant', 'label': 'Tenant', 'label_ar': 'المستأجر', 'type': 'text', 'required': True,
         'synonyms': ['tenant', 'customer', 'client', 'name', 'tenant name', 'المستأجر', 'العميل', 'الاسم', 'اسم المستأجر']},
        {'key': 'invoice_type', 'label': 'Type', 'label_ar': 'النوع', 'type': 'text', 'required': True,
         'synonyms': ['type', 'invoice type', 'category', 'النوع', 'نوع الفاتورة', 'البند', 'التصنيف'],
         'hint': 'e.g. Rent, Utility, Service'},
        {'key': 'amount', 'label': 'Amount', 'label_ar': 'المبلغ', 'type': 'number', 'required': True,
         'synonyms': ['amount', 'total', 'value', 'rent', 'price', 'المبلغ', 'القيمة', 'الإجمالي', 'الايجار', 'الإيجار']},
        {'key': 'issue_date', 'label': 'Issue date', 'label_ar': 'تاريخ الإصدار', 'type': 'date', 'required': True,
         'synonyms': ['issue date', 'date', 'invoice date', 'تاريخ الإصدار', 'تاريخ الفاتورة', 'التاريخ']},
        {'key': 'due_date', 'label': 'Due date', 'label_ar': 'تاريخ الاستحقاق', 'type': 'date', 'required': True,
         'synonyms': ['due date', 'due', 'deadline', 'تاريخ الاستحقاق', 'الاستحقاق', 'موعد الاستحقاق']},
        {'key': 'description', 'label': 'Description', 'label_ar': 'البيان', 'type': 'text', 'required': False,
         'synonyms': ['description', 'details', 'البيان', 'الوصف', 'التفاصيل']},
        {'key': 'knowledge_tax_amount', 'label': 'Knowledge tax', 'label_ar': 'ضريبة المعارف', 'type': 'number', 'required': False,
         'synonyms': ['knowledge tax', 'tax', 'ضريبة المعارف', 'الضريبة', 'ضريبة']},
    ]

    def resolve(self, row, *, user, building, building_id):
        errors, display, clean = {}, {}, {}

        tenant_val = clean_str(row.get('tenant'))
        if not tenant_val:
            errors['tenant'] = 'Required'
        else:
            matches = _resolve_tenant(user, building_id, tenant_val)
            if not matches:
                errors['tenant'] = f"Tenant '{tenant_val}' not found"
            elif len(matches) > 1:
                errors['tenant'] = f"'{tenant_val}' matches {len(matches)} tenants — be more specific"
            else:
                clean['tenant'] = matches[0]
                display['tenant'] = matches[0].name

        inv_type = clean_str(row.get('invoice_type')) or 'Service'
        clean['invoice_type'] = inv_type[:50]
        display['invoice_type'] = clean['invoice_type']

        amt = parse_decimal(row.get('amount'))
        if amt is None or amt <= 0:
            errors['amount'] = 'Invalid amount'
        else:
            clean['amount'] = amt
            display['amount'] = str(amt)

        issue = parse_date(row.get('issue_date'))
        if not issue:
            errors['issue_date'] = 'Invalid or missing date'
        else:
            clean['issue_date'] = issue
            display['issue_date'] = issue.isoformat()

        due = parse_date(row.get('due_date'))
        if not due:
            # Default due date to the issue date when omitted.
            if issue:
                clean['due_date'] = issue
                display['due_date'] = issue.isoformat()
            else:
                errors['due_date'] = 'Invalid or missing date'
        else:
            clean['due_date'] = due
            display['due_date'] = due.isoformat()

        clean['description'] = clean_str(row.get('description'))[:255]
        tax = parse_decimal(row.get('knowledge_tax_amount')) or Decimal('0')
        clean['knowledge_tax_amount'] = tax if tax > 0 else Decimal('0')
        if tax > 0:
            display['knowledge_tax_amount'] = str(tax)

        if errors:
            return None, errors, display
        return clean, errors, display

    def create(self, clean, *, user, building, building_id):
        from billing.models import Invoice, InvoiceLineItem
        from accounting.services import AccountingService
        tax = clean.get('knowledge_tax_amount') or Decimal('0')
        invoice = Invoice.objects.create(
            tenant=clean['tenant'],
            building=building,
            invoice_type=clean['invoice_type'],
            description=clean.get('description', ''),
            issue_date=clean['issue_date'],
            due_date=clean['due_date'],
            total_amount=clean['amount'] + tax,
            knowledge_tax_amount=tax,
            status=Invoice.InvoiceStatus.ISSUED,
        )
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=clean.get('description') or clean['invoice_type'],
            quantity=Decimal('1'),
            unit_price=clean['amount'],
            sort_order=0,
        )
        AccountingService.process_invoice_ledger(invoice)
        return invoice.invoice_number


HANDLERS = {h.key: h() for h in (ExpenseHandler, PaymentHandler, InvoiceHandler)}


def get_handler(resource):
    return HANDLERS.get(resource)


def resolve_building(user, building_id, *, required):
    """Validate building access. Returns (building|None, error|None)."""
    from properties.models import Building
    if building_id in (None, '', 0, '0'):
        if required:
            return None, 'A building is required for this import.'
        return None, None
    try:
        bid = int(building_id)
    except (TypeError, ValueError):
        return None, 'Invalid building.'
    if not user_can_access_building(user, bid):
        return None, 'You do not have access to this building.'
    building = Building.objects.filter(pk=bid).first()
    if not building:
        return None, 'Building not found.'
    return building, None
