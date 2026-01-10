from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from properties.models import Building
from expenses.models import Expense
from accounting.models import LedgerEntry
from expenses.services import ExpenseService

class ExpenseAccountingTest(TestCase):
    
    def setUp(self):
        self.building = Building.objects.create(name="Tower B", address="456 Rd", total_area=2000)

    def test_record_expense_ledger(self):
        expense_data = {
            "building": self.building,
            "category": Expense.ExpenseCategory.MAINTENANCE,
            "description": "Elevator Fix",
            "amount": Decimal('150.00'),
            "expense_date": timezone.now().date()
        }
        
        # Action
        expense = ExpenseService.record_expense(expense_data)
        
        # Verify Ledger
        ct = ContentType.objects.get_for_model(expense)
        entries = LedgerEntry.objects.filter(content_type=ct, object_id=expense.id)
        self.assertEqual(entries.count(), 2)
        
        expense_acc = entries.get(account_type=LedgerEntry.AccountType.EXPENSE)
        asset_acc = entries.get(account_type=LedgerEntry.AccountType.ASSET)
        
        # Invariants
        self.assertEqual(expense_acc.account_name, "Maintenance")
        self.assertEqual(expense_acc.debit, Decimal('150.00')) # Cost increased
        
        self.assertEqual(asset_acc.account_name, "Bank / Cash")
        self.assertEqual(asset_acc.credit, Decimal('150.00')) # Cash decreased
        
        self.assertEqual(sum(e.debit for e in entries), sum(e.credit for e in entries))
