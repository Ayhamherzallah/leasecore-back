from django.db import transaction
from .models import Expense
from accounting.services import AccountingService

class ExpenseService:
    """
    Orchestrates Expense lifecycle.
    """

    @staticmethod
    @transaction.atomic
    def record_expense(expense_data):
        """
        Create Expense -> Trigger Ledger
        """
        # 1. Create Expense
        expense = Expense.objects.create(**expense_data)

        # 2. Trigger Ledger (Cash out)
        AccountingService.process_expense_ledger(expense)

        return expense
