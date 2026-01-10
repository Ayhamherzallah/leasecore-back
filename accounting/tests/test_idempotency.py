from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from .test_invoice_accounting import ReferenceTestCase
from billing.models import Invoice
from accounting.models import LedgerEntry
from billing.services import BillingService
from accounting.services import AccountingService

class IdempotencyTest(ReferenceTestCase):
    
    def test_invoice_issuance_idempotency(self):
        invoice = Invoice.objects.create(
            contract=self.contract,
            tenant=self.tenant,
            invoice_number="INV-IDEM",
            invoice_type=Invoice.InvoiceType.RENT,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            total_amount=Decimal('5000.00'),
            status=Invoice.InvoiceStatus.DRAFT
        )

        # 1. First Call
        BillingService.issue_invoice(invoice)
        initial_count = LedgerEntry.objects.count()
        self.assertEqual(initial_count, 2)
        
        # 2. Duplicate Call (Directly to accounting service to simulate race/retry)
        # Note: BillingService guards against state, but we test lower layer protection too
        AccountingService.process_invoice_ledger(invoice)
        
        # Assert: No new entries
        final_count = LedgerEntry.objects.count()
        self.assertEqual(final_count, initial_count)
