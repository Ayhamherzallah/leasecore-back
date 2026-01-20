from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .test_invoice_accounting import ReferenceTestCase # Reusing setup
from billing.models import Invoice, Payment
from accounting.models import LedgerEntry
from billing.services import BillingService

class PaymentAccountingTest(ReferenceTestCase):
    
    def setUp(self):
        super().setUp()
        # Pre-issue an invoice
        self.invoice = Invoice.objects.create(
            contract=self.contract,
            tenant=self.tenant,
            invoice_number="INV-001",
            invoice_type=Invoice.InvoiceTypeChoices.RENT,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            total_amount=Decimal('5000.00'),
            status=Invoice.InvoiceStatus.DRAFT
        )
        BillingService.issue_invoice(self.invoice)

    def test_partial_payment_ledger(self):
        payment_data = {
            "invoice": self.invoice,
            "amount": Decimal('2000.00'),
            "payment_date": timezone.now().date(),
            "payment_method": Payment.PaymentMethod.BANK_TRANSFER,
            "reference_number": "TXN-1"
        }
        
        # Action
        payment = BillingService.receive_payment(payment_data)
        
        # Verify Invoice State
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.InvoiceStatus.PARTIALLY_PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal('2000.00'))
        
        # Verify Ledger
        ct = ContentType.objects.get_for_model(payment)
        entries = LedgerEntry.objects.filter(content_type=ct, object_id=payment.id)
        self.assertEqual(entries.count(), 2)
        
        bank = entries.get(account_name="Bank / Cash")
        receivable = entries.get(account_name="Accounts Receivable")
        
        self.assertEqual(bank.debit, Decimal('2000.00')) # Cash In
        self.assertEqual(receivable.credit, Decimal('2000.00')) # Debt Reduced
        
        # Balance Check
        self.assertEqual(sum(e.debit for e in entries), sum(e.credit for e in entries))

    def test_full_payment_ledger(self):
        payment_data = {
            "invoice": self.invoice,
            "amount": Decimal('5000.00'),
            "payment_date": timezone.now().date(),
            "payment_method": Payment.PaymentMethod.CASH,
            "reference_number": "TXN-FULL"
        }
        
        BillingService.receive_payment(payment_data)
        
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.InvoiceStatus.PAID)
        self.assertEqual(self.invoice.paid_amount, Decimal('5000.00'))
