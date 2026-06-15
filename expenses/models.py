from django.db import models
from django.utils.translation import gettext_lazy as _


class ExpenseCategory(models.Model):
    # Owner building — private per vendor. NULL = shared system default.
    building = models.ForeignKey(
        'properties.Building',
        on_delete=models.CASCADE,
        related_name='expense_categories',
        null=True,
        blank=True,
        db_index=True,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Expense Categories"
        unique_together = (('building', 'name'),)
        ordering = ['name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    class CostType(models.TextChoices):
        DYNAMIC = 'DYNAMIC', _('Dynamic (one-off)')
        FIXED = 'FIXED', _('Fixed (recurring)')

    building = models.ForeignKey('properties.Building', on_delete=models.PROTECT, related_name='expenses')
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True, help_text="If expense is specific to a unit")
    
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    cost_type = models.CharField(max_length=10, choices=CostType.choices, default=CostType.DYNAMIC, db_index=True)
    description = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255, blank=True)
    expense_for = models.CharField(max_length=255, blank=True, help_text="Custom description for the PDF (As Expense Of)")
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(db_index=True)
    
    # Traceability
    invoice_reference = models.CharField(max_length=100, blank=True, help_text="Vendor Invoice Number")
    attachment = models.FileField(upload_to='expenses/%Y/%m/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date']

    def __str__(self):
        return f"{self.category}: {self.amount}"


class FixedCost(models.Model):
    """
    A recurring expense template (salaries, cleaning, security, internet…).
    Generates FixedCostOccurrence rows that, once confirmed, become real
    immutable Expense records posted to the ledger.
    """
    class Frequency(models.TextChoices):
        WEEKLY = 'WEEKLY', _('Weekly')
        MONTHLY = 'MONTHLY', _('Monthly')
        QUARTERLY = 'QUARTERLY', _('Quarterly')
        SEMIANNUAL = 'SEMIANNUAL', _('Semi-annual')
        YEARLY = 'YEARLY', _('Yearly')
        CUSTOM = 'CUSTOM', _('Custom interval')

    class CustomUnit(models.TextChoices):
        DAY = 'DAY', _('Days')
        WEEK = 'WEEK', _('Weeks')
        MONTH = 'MONTH', _('Months')

    building = models.ForeignKey('properties.Building', on_delete=models.PROTECT, related_name='fixed_costs', db_index=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='fixed_costs')
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True, related_name='fixed_costs')

    name = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    frequency = models.CharField(max_length=12, choices=Frequency.choices, default=Frequency.MONTHLY)
    custom_interval = models.PositiveIntegerField(null=True, blank=True, help_text="For CUSTOM frequency")
    custom_unit = models.CharField(max_length=6, choices=CustomUnit.choices, null=True, blank=True)

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, help_text="Optional: stop generating after this date")
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"


class FixedCostOccurrence(models.Model):
    """A single scheduled instance of a FixedCost for a given period."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        CONFIRMED = 'CONFIRMED', _('Confirmed')
        SKIPPED = 'SKIPPED', _('Skipped')

    fixed_cost = models.ForeignKey(FixedCost, on_delete=models.CASCADE, related_name='occurrences')
    period_date = models.DateField(db_index=True, help_text="The period this occurrence covers")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    expense = models.OneToOneField(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name='fixed_cost_occurrence')

    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['period_date']
        unique_together = (('fixed_cost', 'period_date'),)

    def __str__(self):
        return f"{self.fixed_cost.name} @ {self.period_date} [{self.status}]"
