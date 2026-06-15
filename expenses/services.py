import calendar
from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from .models import Expense, FixedCost, FixedCostOccurrence
from accounting.services import AccountingService


class ExpenseService:
    """Orchestrates Expense lifecycle."""

    @staticmethod
    @transaction.atomic
    def record_expense(expense_data):
        """Create Expense -> Trigger Ledger (cash out)."""
        expense = Expense.objects.create(**expense_data)
        AccountingService.process_expense_ledger(expense)
        return expense


def _add_months(d, months):
    """Add N months to a date, clamping the day to the month's last day."""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# Maps each frequency to a (kind, n) step where kind is 'months' or 'days'.
_FREQ_STEP = {
    FixedCost.Frequency.WEEKLY: ('days', 7),
    FixedCost.Frequency.MONTHLY: ('months', 1),
    FixedCost.Frequency.QUARTERLY: ('months', 3),
    FixedCost.Frequency.SEMIANNUAL: ('months', 6),
    FixedCost.Frequency.YEARLY: ('months', 12),
}

_MAX_PERIODS = 600  # safety cap to avoid runaway loops


class FixedCostService:
    """
    Recurring fixed costs.

    Workflow (manual generation, confirm-to-post):
      1. Create a FixedCost template.
      2. `generate_due` creates PENDING occurrences up to today.
      3. `confirm_occurrence` turns a PENDING occurrence into a real Expense
         (posting to the ledger). `skip_occurrence` dismisses it.
    """

    @staticmethod
    def _step(fixed_cost, d):
        """Return the next period date after `d` for this fixed cost."""
        freq = fixed_cost.frequency
        if freq == FixedCost.Frequency.CUSTOM:
            interval = fixed_cost.custom_interval or 1
            unit = fixed_cost.custom_unit or FixedCost.CustomUnit.MONTH
            if unit == FixedCost.CustomUnit.DAY:
                return d + timedelta(days=interval)
            if unit == FixedCost.CustomUnit.WEEK:
                return d + timedelta(weeks=interval)
            return _add_months(d, interval)
        kind, n = _FREQ_STEP.get(freq, ('months', 1))
        return d + timedelta(days=n) if kind == 'days' else _add_months(d, n)

    @classmethod
    def due_periods(cls, fixed_cost, until=None):
        """All period dates from start_date up to `until` (default today)."""
        until = until or timezone.now().date()
        if fixed_cost.end_date:
            until = min(until, fixed_cost.end_date)
        periods = []
        d = fixed_cost.start_date
        count = 0
        while d <= until and count < _MAX_PERIODS:
            periods.append(d)
            d = cls._step(fixed_cost, d)
            count += 1
        return periods

    @classmethod
    @transaction.atomic
    def generate_due(cls, fixed_cost, until=None):
        """
        Create PENDING occurrences for any period not yet materialised.
        Returns the list of newly created occurrences. Inactive templates
        generate nothing.
        """
        if not fixed_cost.is_active:
            return []
        existing = set(
            fixed_cost.occurrences.values_list('period_date', flat=True)
        )
        created = []
        for period in cls.due_periods(fixed_cost, until=until):
            if period in existing:
                continue
            created.append(FixedCostOccurrence.objects.create(
                fixed_cost=fixed_cost,
                period_date=period,
                amount=fixed_cost.amount,
                status=FixedCostOccurrence.Status.PENDING,
            ))
        return created

    @staticmethod
    @transaction.atomic
    def confirm_occurrence(occurrence, paid_date=None):
        """
        Turn a PENDING occurrence into an immutable Expense posted to the ledger.
        Idempotent: confirming an already-confirmed occurrence is a no-op.
        """
        if occurrence.status == FixedCostOccurrence.Status.CONFIRMED:
            return occurrence.expense

        fc = occurrence.fixed_cost
        expense = ExpenseService.record_expense({
            'building': fc.building,
            'unit': fc.unit,
            'category': fc.category,
            'cost_type': Expense.CostType.FIXED,
            'description': fc.name,
            'vendor_name': fc.vendor_name,
            'expense_for': fc.name,
            'amount': occurrence.amount,
            'expense_date': paid_date or occurrence.period_date,
        })

        occurrence.expense = expense
        occurrence.status = FixedCostOccurrence.Status.CONFIRMED
        occurrence.confirmed_at = timezone.now()
        occurrence.save(update_fields=['expense', 'status', 'confirmed_at'])
        return expense

    @staticmethod
    @transaction.atomic
    def skip_occurrence(occurrence):
        """Dismiss a PENDING occurrence (won't post to the ledger)."""
        if occurrence.status == FixedCostOccurrence.Status.CONFIRMED:
            raise ValueError("Cannot skip a confirmed occurrence.")
        occurrence.status = FixedCostOccurrence.Status.SKIPPED
        occurrence.save(update_fields=['status'])
        return occurrence
