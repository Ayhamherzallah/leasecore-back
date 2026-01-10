from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from properties.models import Building, Floor, Unit
from tenants.models import Tenant, Contract
from billing.models import Invoice
from accounting.models import LedgerEntry
from billing.services import BillingService

class ReferenceTestCase(TestCase):
    """Base class to setup common financial context"""
    def setUp(self):
        # 1. Physical Assets
        self.building = Building.objects.create(name="Tower A", address="123 St", total_area=1000)
        self.floor = Floor.objects.create(building=self.building, name="G", number=0)
        self.unit = Unit.objects.create(
            floor=self.floor, unit_number="101", 
            area=100, market_rent=5000
        )
        
        # 2. Legal Context
        self.tenant = Tenant.objects.create(name="John Doe", national_id="123")
        self.contract = Contract.objects.create(
            tenant=self.tenant, unit=self.unit,
            start_date=timezone.now().date(),
            end_date=timezone.now().date(),
            rent_amount=5000,
            payment_frequency="MONTHLY"
        )

class InvoiceAccountingTest(ReferenceTestCase):
    
    def test_invoice_issuance_creates_balanced_ledger(self):
        # Setup Draft Invoice
        invoice = Invoice.objects.create(
            contract=self.contract,
            tenant=self.tenant,
            invoice_number="INV-001",
            invoice_type=Invoice.InvoiceType.RENT,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date(),
            total_amount=Decimal('5000.00'),
            status=Invoice.InvoiceStatus.DRAFT
        )

        # Action: Service Call
        BillingService.issue_invoice(invoice)
        
        # Verification
        # 1. State Update
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.InvoiceStatus.ISSUED)

        # 2. Ledger Entries
        ct = ContentType.objects.get_for_model(invoice)
        entries = LedgerEntry.objects.filter(content_type=ct, object_id=invoice.id)
        self.assertEqual(entries.count(), 2)
        
        receivable = entries.get(account_name="Accounts Receivable")
        revenue = entries.get(account_name="Rental Income")
        
        # 3. Financial Invariants
        self.assertEqual(receivable.debit, Decimal('5000.00'))
        self.assertEqual(receivable.credit, Decimal('0.00'))
        
        self.assertEqual(revenue.debit, Decimal('0.00'))
        self.assertEqual(revenue.credit, Decimal('5000.00'))
        
        # 4. Global Balance
        total_dr = sum(e.debit for e in entries)
        total_cr = sum(e.credit for e in entries)
        self.assertEqual(total_dr, total_cr)
