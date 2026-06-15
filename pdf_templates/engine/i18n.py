"""Localization for PDF documents — each document renders in ONE language."""

import datetime

AR = 'ar'
EN = 'en'


def normalize_lang(lang):
    if lang and str(lang).lower().startswith('ar'):
        return AR
    return EN


def is_rtl(lang):
    return normalize_lang(lang) == AR


# ── String tables ────────────────────────────────────────────────────────

STRINGS = {
    EN: {
        'invoice_title': 'Invoice',
        'receipt_title': 'Payment Receipt',
        'expense_title': 'Expense Voucher',
        'ledger_title': 'General Ledger',
        'sample_title': 'Sample Document',

        'bill_to': 'Bill To',
        'invoice_details': 'Invoice Details',
        'details': 'Details',
        'received_from': 'Received From',
        'paid_to': 'Paid To',
        'receipt_details': 'Receipt Details',
        'voucher_details': 'Voucher Details',

        'issue_date': 'Issue Date',
        'due_date': 'Due Date',
        'date': 'Date',
        'type': 'Type',
        'category': 'Category',
        'unit': 'Unit',
        'reference': 'Reference',
        'payment_method': 'Payment Method',
        'paid_by': 'Paid By',
        'description': 'Description',
        'qty': 'Qty',
        'unit_price': 'Unit Price',
        'amount': 'Amount',

        'subtotal': 'Subtotal',
        'knowledge_tax': 'Knowledge Tax',
        'total': 'Total',
        'paid': 'Paid',
        'balance_due': 'Balance Due',
        'the_sum_of': 'The Sum Of',
        'as_payment_of': 'As Payment Of',
        'for': 'For',

        'notes': 'Notes',
        'received_by': 'Received By',
        'authorized_signature': 'Authorized Signature',
        'signature': 'Signature',
        'page': 'Page',
        'currency': 'JOD',
        'cash_client': 'Cash Client',
        'petty_cash': 'Petty Cash',
        'general_account': 'General Account',

        'col_date': 'Date',
        'col_account': 'Account',
        'col_description': 'Description',
        'col_debit': 'Debit',
        'col_credit': 'Credit',
        'sample_line': 'Monthly Rent — Unit 101',
    },
    AR: {
        'invoice_title': 'فاتورة',
        'receipt_title': 'سند قبض',
        'expense_title': 'سند صرف',
        'ledger_title': 'دفتر الأستاذ العام',
        'sample_title': 'مستند تجريبي',

        'bill_to': 'الفاتورة إلى',
        'invoice_details': 'تفاصيل الفاتورة',
        'details': 'التفاصيل',
        'received_from': 'استلمنا من',
        'paid_to': 'صرفنا إلى',
        'receipt_details': 'تفاصيل السند',
        'voucher_details': 'تفاصيل السند',

        'issue_date': 'تاريخ الإصدار',
        'due_date': 'تاريخ الاستحقاق',
        'date': 'التاريخ',
        'type': 'النوع',
        'category': 'التصنيف',
        'unit': 'الوحدة',
        'reference': 'المرجع',
        'payment_method': 'طريقة الدفع',
        'paid_by': 'المُسدِّد',
        'description': 'البيان',
        'qty': 'الكمية',
        'unit_price': 'السعر',
        'amount': 'المبلغ',

        'subtotal': 'المجموع الفرعي',
        'knowledge_tax': 'ضريبة المعارف',
        'total': 'الإجمالي',
        'paid': 'المدفوع',
        'balance_due': 'المبلغ المتبقي',
        'the_sum_of': 'مبلغ وقدره',
        'as_payment_of': 'وذلك عن',
        'for': 'عن',

        'notes': 'ملاحظات',
        'received_by': 'المستلم',
        'authorized_signature': 'التوقيع المعتمد',
        'signature': 'التوقيع',
        'page': 'صفحة',
        'currency': 'د.أ',
        'cash_client': 'عميل نقدي',
        'petty_cash': 'مصروف نثري',
        'general_account': 'حساب عام',

        'col_date': 'التاريخ',
        'col_account': 'الحساب',
        'col_description': 'البيان',
        'col_debit': 'مدين',
        'col_credit': 'دائن',
        'sample_line': 'إيجار شهري — وحدة 101',
    },
}


INVOICE_STATUS = {
    'PAID': {EN: 'Paid', AR: 'مدفوعة'},
    'PARTIALLY_PAID': {EN: 'Partially Paid', AR: 'مدفوعة جزئياً'},
    'ISSUED': {EN: 'Issued', AR: 'صادرة'},
    'DRAFT': {EN: 'Draft', AR: 'مسودة'},
    'OVERDUE': {EN: 'Overdue', AR: 'متأخرة'},
    'VOID': {EN: 'Void', AR: 'ملغاة'},
}

PAYMENT_METHOD = {
    'CASH': {EN: 'Cash', AR: 'نقداً'},
    'CHECK': {EN: 'Cheque', AR: 'شيك'},
    'TRANSFER': {EN: 'Bank Transfer', AR: 'تحويل بنكي'},
    'POS': {EN: 'Card / POS', AR: 'بطاقة / نقاط بيع'},
}

_MONTHS_AR = [
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
]


class Localizer:
    """Bundles language, direction, and string lookups for a single document."""

    def __init__(self, lang):
        self.lang = normalize_lang(lang)
        self.rtl = self.lang == AR

    def t(self, key):
        return STRINGS[self.lang].get(key, STRINGS[EN].get(key, key))

    def status(self, code):
        entry = INVOICE_STATUS.get(code)
        if not entry:
            return code
        return entry.get(self.lang, code)

    def method(self, code):
        entry = PAYMENT_METHOD.get(code)
        if not entry:
            return code
        return entry.get(self.lang, code)

    def date(self, value):
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.date.fromisoformat(value[:10])
            except ValueError:
                return value
        if not isinstance(value, (datetime.date, datetime.datetime)):
            return str(value)
        if self.lang == AR:
            return f'{value.day} {_MONTHS_AR[value.month - 1]} {value.year}'
        return value.strftime('%d %b %Y')

    def money(self, amount):
        try:
            num = f'{float(amount):,.2f}'
        except (TypeError, ValueError):
            num = str(amount)
        cur = self.t('currency')
        # Currency symbol trails the number in both directions for clarity.
        return f'{num} {cur}'

    def number(self, amount, decimals=2):
        try:
            return f'{float(amount):,.{decimals}f}'
        except (TypeError, ValueError):
            return str(amount)
