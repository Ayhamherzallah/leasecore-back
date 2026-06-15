from io import BytesIO
from decimal import Decimal

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

from .renderer import DocRenderer
from .styles import get_style
from .i18n import Localizer
from .branding import (
    resolve_theme,
    theme_from_invoice,
    theme_from_payment,
    theme_from_expense,
)


def _buffer():
    return BytesIO()


def _new(theme, lang):
    loc = Localizer(lang)
    buffer = _buffer()
    width, height = A4
    c = canvas.Canvas(buffer, pagesize=A4)
    r = DocRenderer(c, width, height, theme, loc, get_style(theme.template))
    return buffer, c, r, loc


def _status_color(theme, code):
    return {
        'PAID': theme.success,
        'PARTIALLY_PAID': theme.primary,
        'ISSUED': theme.primary,
        'DRAFT': theme.gray,
        'OVERDUE': theme.danger,
        'VOID': theme.danger,
    }.get(code, theme.gray)


# ── Invoice ───────────────────────────────────────────────────────────────

def generate_invoice_pdf(invoice, theme=None, lang='en'):
    theme = theme or theme_from_invoice(invoice)
    buffer, c, r, loc = _new(theme, lang)

    title = loc.t('invoice_title')
    ref = f'#{invoice.invoice_number}'
    status = (loc.status(invoice.status), _status_color(theme, invoice.status))

    tenant_name = invoice.tenant.name if invoice.tenant else loc.t('cash_client')
    phone = getattr(invoice.tenant, 'phone', '') if invoice.tenant else ''
    party = {'label': loc.t('bill_to'), 'name': tenant_name, 'sub': phone or None}

    type_label = invoice.invoice_type.replace('_', ' ').strip()
    meta = [
        (loc.t('issue_date'), loc.date(invoice.issue_date)),
        (loc.t('due_date'), loc.date(invoice.due_date)),
        (loc.t('type'), type_label),
    ]
    if invoice.contract and invoice.contract.unit:
        meta.append((loc.t('unit'), invoice.contract.unit.unit_number))

    line_items = list(invoice.line_items.all())
    if line_items:
        rows_data = [(it.description, it.quantity, it.unit_price, it.line_total) for it in line_items]
    else:
        desc = (invoice.description or '').strip() or type_label
        if invoice.contract and invoice.contract.unit:
            desc = f'{desc} — {loc.t("unit")} {invoice.contract.unit.unit_number}'
        tax = invoice.knowledge_tax_amount or Decimal('0')
        amt = invoice.total_amount - tax
        rows_data = [(desc, Decimal('1'), amt, amt)]

    subtotal = sum((ld for _, _, _, ld in rows_data), Decimal('0'))
    rows = [
        (desc, loc.number(qty), loc.number(unit), loc.number(line_total))
        for desc, qty, unit, line_total in rows_data
    ]

    tax_amount = invoice.knowledge_tax_amount or Decimal('0')
    balance = invoice.total_amount - invoice.paid_amount
    totals = [(loc.t('subtotal'), subtotal, False, False)]
    if tax_amount > 0:
        totals.append((loc.t('knowledge_tax'), tax_amount, False, False))
    totals.append((loc.t('total'), invoice.total_amount, True, False))
    totals.append((loc.t('paid'), invoice.paid_amount, False, False))
    if balance > 0:
        totals.append((loc.t('balance_due'), balance, False, True))

    y = r.header(title, ref, status)
    y = r.info_block(y, party, meta)
    y = r.items_table(y, rows)
    y = r.notes(y, loc.t('notes'), invoice.notes)
    r.totals(y - 4, totals)
    r.footer()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ── Receipt ───────────────────────────────────────────────────────────────

def generate_receipt_pdf(payment, theme=None, lang='en'):
    theme = theme or theme_from_payment(payment)
    buffer, c, r, loc = _new(theme, lang)

    ref = payment.reference_number or str(payment.id)
    client = loc.t('cash_client')
    if payment.invoice and payment.invoice.tenant:
        client = payment.invoice.tenant.name

    party = {'label': loc.t('received_from'), 'name': client,
             'sub': (payment.paid_by or None)}

    method = loc.method(payment.payment_method)
    if payment.payment_method == 'CHECK' and payment.cheques.exists():
        chk = payment.cheques.first()
        method = f'{method} — {chk.bank_name}'
    meta = [
        (loc.t('date'), loc.date(payment.payment_date)),
        (loc.t('payment_method'), method),
        (loc.t('reference'), payment.reference_number or '—'),
    ]
    desc = payment.payment_for
    if not desc and payment.invoice:
        desc = f'{loc.t("for")} #{payment.invoice.invoice_number}'

    y = r.header(loc.t('receipt_title'), f'#{ref}', None)
    y = r.info_block(y, party, meta)
    y = r.amount_highlight(y, loc.t('the_sum_of'), loc.money(payment.amount))
    if desc:
        y = r.notes(y, loc.t('as_payment_of'), desc)
    r.signatures(110, [loc.t('received_by'), loc.t('authorized_signature')])
    r.footer()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ── Expense ─────────────────────────────────────────────────────────────────

def generate_expense_pdf(expense, theme=None, lang='en'):
    theme = theme or theme_from_expense(expense)
    buffer, c, r, loc = _new(theme, lang)

    ref = expense.invoice_reference or str(expense.id)
    payee = expense.vendor_name or loc.t('petty_cash')
    party = {'label': loc.t('paid_to'), 'name': payee, 'sub': None}

    cat = expense.category.name if expense.category else '—'
    meta = [
        (loc.t('date'), loc.date(expense.expense_date)),
        (loc.t('category'), cat),
        (loc.t('reference'), ref),
    ]
    desc = expense.expense_for or expense.description or ''
    if not expense.expense_for:
        if getattr(expense, 'unit', None):
            desc = f'{desc} — {loc.t("unit")} {expense.unit.unit_number}'
        elif getattr(expense, 'building', None):
            desc = f'{desc} — {expense.building.name}'

    y = r.header(loc.t('expense_title'), f'#{ref}', None)
    y = r.info_block(y, party, meta)
    y = r.amount_highlight(y, loc.t('the_sum_of'), loc.money(expense.amount))
    if desc:
        y = r.notes(y, loc.t('as_payment_of'), desc)
    r.signatures(110, [loc.t('received_by'), loc.t('authorized_signature')])
    r.footer()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ── Ledger report ─────────────────────────────────────────────────────────

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


def generate_ledger_report(entries, date_range_text=None, theme=None, building_id=None, lang='en'):
    theme = theme or resolve_theme(building_id)
    buffer, c, r, loc = _new(theme, lang)

    def account(name):
        return ACCOUNT_TRANSLATIONS.get(name, name) if loc.rtl else name

    cw = r.content_w
    date_b = cw * 0.16
    acct_b = cw * 0.42
    desc_b = cw * 0.70
    debit_b = cw * 0.85
    credit_b = cw

    def header_row(y):
        return r._table_header(y, [
            ('start', 0, date_b, loc.t('col_date')),
            ('start', date_b, acct_b, loc.t('col_account')),
            ('start', acct_b, desc_b, loc.t('col_description')),
            ('end', desc_b, debit_b, loc.t('col_debit')),
            ('end', debit_b, credit_b, loc.t('col_credit')),
        ])

    y = r.header(loc.t('ledger_title'), date_range_text or '', None)
    y = header_row(y)
    total_debit = total_credit = Decimal('0')

    for e in entries:
        if y < 90:
            r.footer()
            c.showPage()
            y = r.header(loc.t('ledger_title'), date_range_text or '', None)
            y = header_row(y)
        desc = r._truncate(e.description, r.font, 9, (desc_b - acct_b) - 14)
        r._cell('start', 0, date_b, y, loc.date(e.transaction_date), r.font, 9, theme.dark)
        r._cell('start', date_b, acct_b, y, account(e.account_name), r.font, 9, theme.dark)
        r._cell('start', acct_b, desc_b, y, desc, r.font, 9, theme.dark)
        r._cell('end', desc_b, debit_b, y, loc.number(e.debit) if e.debit > 0 else '—', r.font, 9, theme.dark)
        r._cell('end', debit_b, credit_b, y, loc.number(e.credit) if e.credit > 0 else '—', r.font, 9, theme.dark)
        r.rule(y - 12, HexColor('#eef1f4'), 0.5)
        y -= 22
        total_debit += e.debit
        total_credit += e.credit

    y -= 6
    r.rule(y + 10, theme.primary, 1)
    r._cell('start', acct_b, desc_b, y - 4, loc.t('total'), r.font_bold, 10, theme.secondary)
    r._cell('end', desc_b, debit_b, y - 4, loc.number(total_debit), r.font_bold, 10, theme.secondary)
    r._cell('end', debit_b, credit_b, y - 4, loc.number(total_credit), r.font_bold, 10, theme.secondary)

    r.footer()
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


# ── Sample / preview ─────────────────────────────────────────────────────────

def generate_sample_pdf(theme=None, building_id=None, lang='en'):
    theme = theme or resolve_theme(building_id)
    buffer, c, r, loc = _new(theme, lang)

    title = loc.t('invoice_title')
    status = (loc.status('ISSUED'), _status_color(theme, 'ISSUED'))
    party = {'label': loc.t('bill_to'), 'name': loc.t('cash_client'), 'sub': '+962 7 0000 0000'}
    meta = [
        (loc.t('issue_date'), loc.date('2026-01-01')),
        (loc.t('due_date'), loc.date('2026-01-31')),
        (loc.t('type'), 'Rent' if not loc.rtl else 'إيجار'),
        (loc.t('unit'), '101'),
    ]
    rows = [
        (loc.t('sample_line'), loc.number(1), loc.number(1250), loc.number(1250)),
        (('Service Fee' if not loc.rtl else 'رسوم خدمة'), loc.number(1), loc.number(75), loc.number(75)),
    ]
    totals = [
        (loc.t('subtotal'), Decimal('1325'), False, False),
        (loc.t('total'), Decimal('1325'), True, False),
        (loc.t('paid'), Decimal('500'), False, False),
        (loc.t('balance_due'), Decimal('825'), False, True),
    ]

    y = r.header(title, '#INV-PREVIEW-001', status)
    y = r.info_block(y, party, meta)
    y = r.items_table(y, rows)
    r.totals(y - 4, totals)
    r.footer()

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer
