from django.db import models
from django.utils.translation import gettext_lazy as _

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Expense Categories"
        
    def __str__(self):
        return self.name

class Expense(models.Model):
    building = models.ForeignKey('properties.Building', on_delete=models.PROTECT, related_name='expenses')
    unit = models.ForeignKey('properties.Unit', on_delete=models.SET_NULL, null=True, blank=True, help_text="If expense is specific to a unit")
    
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description = models.CharField(max_length=255)
    vendor_name = models.CharField(max_length=255, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField(db_index=True)
    
    # Traceability
    invoice_reference = models.CharField(max_length=100, blank=True, help_text="Vendor Invoice Number")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date']

    def __str__(self):
        return f"{self.category}: {self.amount}"
