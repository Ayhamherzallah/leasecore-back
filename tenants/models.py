from django.db import models
from django.utils.translation import gettext_lazy as _

class Tenant(models.Model):
    class TenantType(models.TextChoices):
        INDIVIDUAL = 'INDIVIDUAL', _('Individual')
        COMPANY = 'COMPANY', _('Company')

    name = models.CharField(max_length=255)
    tenant_type = models.CharField(max_length=20, choices=TenantType.choices, default=TenantType.INDIVIDUAL)
    
    # Identity
    national_id = models.CharField(max_length=50, blank=True, help_text="National ID or Tax Registration Number")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['national_id']),
        ]

    def __str__(self):
        return self.name

class Contract(models.Model):
    class ContractStatus(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        ACTIVE = 'ACTIVE', _('Active')
        EXPIRED = 'EXPIRED', _('Expired')
        TERMINATED = 'TERMINATED', _('Terminated')

    class PaymentFrequency(models.TextChoices):
        MONTHLY = 'MONTHLY', _('Monthly')
        QUARTERLY = 'QUARTERLY', _('Quarterly')
        BIANNUALLY = 'BIANNUALLY', _('Bi-Annually')
        YEARLY = 'YEARLY', _('Yearly')

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name='contracts')
    unit = models.ForeignKey('properties.Unit', on_delete=models.PROTECT, related_name='contracts')
    
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    
    rent_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Rent per period")
    payment_frequency = models.CharField(max_length=20, choices=PaymentFrequency.choices)
    security_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.DRAFT, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"Contract #{self.id} - {self.tenant.name}"
