# Signals are now strictly for logging or non-financial side effects.
# STRICT POLICY: No ledger entries are created here.
# All ledger entries MUST be created via explicit Service calls.

from django.db.models.signals import post_save
from django.dispatch import receiver
from billing.models import Invoice, Payment
from expenses.models import Expense

@receiver(post_save, sender=Invoice)
def log_invoice_change(sender, instance, created, **kwargs):
    pass # Logging only

@receiver(post_save, sender=Payment)
def log_payment_change(sender, instance, created, **kwargs):
    pass # Logging only

@receiver(post_save, sender=Expense)
def log_expense_change(sender, instance, created, **kwargs):
    pass # Logging only
