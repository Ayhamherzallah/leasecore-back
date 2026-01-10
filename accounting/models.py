from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

class LedgerEntry(models.Model):
    """
    Represents a single line in the General Ledger. 
    Double-entry is enforced by logic (not schema), ensuring Sum(debit) == Sum(credit) per transaction group.
    """
    class AccountType(models.TextChoices):
        ASSET = 'ASSET', _('Asset')
        LIABILITY = 'LIABILITY', _('Liability')
        EQUITY = 'EQUITY', _('Equity')
        REVENUE = 'REVENUE', _('Revenue')
        EXPENSE = 'EXPENSE', _('Expense')

    building = models.ForeignKey('properties.Building', on_delete=models.PROTECT, related_name='ledger_entries')
    
    transaction_date = models.DateField(db_index=True)
    description = models.CharField(max_length=255)
    
    # Account Information (Can be a simple string or a separate ChartOfAccounts model if complexity increases)
    account_name = models.CharField(max_length=100, db_index=True, help_text="e.g., Accounts Receivable, Bank, Rental Income")
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    
    # Generic Relation to Source Document (Invoice, Payment, Expense)
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    source_object = GenericForeignKey('content_type', 'object_id')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id']), # Fast lookup by source
            models.Index(fields=['transaction_date']),
            models.Index(fields=['account_name']),
        ]
        verbose_name_plural = "Ledger Entries"

    def __str__(self):
        return f"{self.transaction_date} | {self.account_name} | Dr:{self.debit} Cr:{self.credit}"
