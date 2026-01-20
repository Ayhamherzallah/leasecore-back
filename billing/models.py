from django.db import models
from django.utils.translation import gettext_lazy as _

class InvoiceType(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g. Rent, Utility, Service Fee")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Invoice(models.Model):
    # Removed strict choices to allow dynamic types
    # Legacy choices for reference or default populating
    class InvoiceTypeChoices(models.TextChoices):
        RENT = 'RENT', _('Rent')
        UTILITY = 'UTILITY', _('Utility')
        SERVICE = 'SERVICE', _('Service Fee')
        PENALTY = 'PENALTY', _('Late Penalty')

    class InvoiceStatus(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        ISSUED = 'ISSUED', _('Issued')
        PAID = 'PAID', _('Paid')
        PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
        VOID = 'VOID', _('Void')
        OVERDUE = 'OVERDUE', _('Overdue')

    contract = models.ForeignKey('tenants.Contract', on_delete=models.PROTECT, related_name='invoices', null=True, blank=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.PROTECT, related_name='invoices')
    
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    # Changed: Removed choices=... to allow dynamic strings from InvoiceType model
    invoice_type = models.CharField(max_length=50) 
    description = models.CharField(max_length=255, blank=True, help_text="Custom description for the PDF (Description / البيان)")
    issue_date = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return f"INV-{self.invoice_number}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            import uuid
            import time
            # Format: INV-YYYYMMDD-XXXX
            from django.utils import timezone
            now = timezone.now()
            date_str = now.strftime('%Y%m%d')
            uid = str(uuid.uuid4())[:4].upper()
            self.invoice_number = f"INV-{date_str}-{uid}"
        super().save(*args, **kwargs)

class UtilityBill(models.Model):
    """
    Represents a meter reading event that generates a cost.
    Usually triggers an invoice (or is a line item on one).
    """
    class UtilityType(models.TextChoices):
        ELECTRICITY = 'ELECTRICITY', _('Electricity')
        WATER = 'WATER', _('Water')
        AC = 'AC', _('A/C (BTU)')

    unit = models.ForeignKey('properties.Unit', on_delete=models.CASCADE, related_name='utility_bills')
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='utility_readings')
    
    utility_type = models.CharField(max_length=20, choices=UtilityType.choices)
    previous_reading = models.DecimalField(max_digits=12, decimal_places=2)
    current_reading = models.DecimalField(max_digits=12, decimal_places=2)
    consumption = models.DecimalField(max_digits=12, decimal_places=2)
    rate_per_unit = models.DecimalField(max_digits=10, decimal_places=4)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    reading_date = models.DateField(db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utility_type} - {self.reading_date}"

class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = 'TRANSFER', _('Bank Transfer')
        CHECK = 'CHECK', _('Check')
        CASH = 'CASH', _('Cash')
        POS = 'POS', _('Point of Sale')

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(db_index=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference_number = models.CharField(max_length=100, blank=True, help_text="Check number or Transaction identifier")
    proof_document = models.FileField(upload_to='payments/%Y/%m/', blank=True, null=True)
    notes = models.TextField(blank=True, help_text="Internal notes or additional comments")
    payment_for = models.CharField(max_length=255, blank=True, help_text="Description of what is being paid for (As Payment Of)")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PAY-{self.id} for {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            import uuid
            self.reference_number = f"PAY-{str(uuid.uuid4())[:8].upper()}"
        super().save(*args, **kwargs)

class Cheque(models.Model):
    class ChequeStatus(models.TextChoices):
        RECEIVED = 'RECEIVED', _('Received (In Hand)')     # شيك بالخزينة
        DEPOSITED = 'DEPOSITED', _('Deposited')           # برسم التحصيل
        CLEARED = 'CLEARED', _('Cleared (Collected)')     # محصل
        BOUNCED = 'BOUNCED', _('Bounced (Returned)')      # مرتجع
        RETURNED_BY_US = 'RETURNED_BY_US', _('Returned to Tenant') # مرتجع للمستأجر

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='cheques')
    cheque_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    drawer_name = models.CharField(max_length=150, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    cheque_date = models.DateField(help_text="The date written on the cheque (Due Date)")
    
    status = models.CharField(max_length=20, choices=ChequeStatus.choices, default=ChequeStatus.RECEIVED)
    
    cheque_image = models.FileField(upload_to='cheques/', blank=True, null=True, help_text="Scanned copy of the cheque")
    deposit_image = models.FileField(upload_to='deposits/', blank=True, null=True, help_text="Bank deposit slip")
    
    # Lifecycle Tracking
    cleared_date = models.DateField(null=True, blank=True)
    bounced_date = models.DateField(null=True, blank=True)
    bounce_reason = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['cheque_date']
        verbose_name = _("Cheque")
        verbose_name_plural = _("Cheques")

    def __str__(self):
        return f"CHQ-{self.cheque_number} - {self.status}"
