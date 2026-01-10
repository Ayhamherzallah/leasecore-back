from django.contrib import admin
from .models import Invoice, Payment, UtilityBill

# NOTE: InvoiceItem model does not exist in standard spec, removing inline.
# If itemized invoices are needed later, a model migration is required.

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "tenant", "invoice_type", "total_amount", "paid_amount", "status", "issue_date", "due_date")
    list_filter = ("status", "invoice_type", "issue_date")
    search_fields = ("invoice_number", "tenant__name")
    readonly_fields = ("paid_amount",) 

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "invoice", "payment_date", "amount", "payment_method")
    list_filter = ("payment_date", "payment_method")
    search_fields = ("reference_number", "invoice__invoice_number")
    autocomplete_fields = ["invoice"]

@admin.register(UtilityBill)
class UtilityBillAdmin(admin.ModelAdmin):
    # Fixed: Removed 'period_start' and 'period_end' which are not fields in the model
    # Replacing with 'reading_date' and 'consumption'
    list_display = ("unit", "utility_type", "reading_date", "consumption", "amount")
    list_filter = ("utility_type",)
    
    # Optional: If you want to show which invoice it belongs to
    raw_id_fields = ("invoice", "unit")
