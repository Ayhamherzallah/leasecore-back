from django.contrib import admin
from .models import LedgerEntry

@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("transaction_date", "account_name", "account_type", "debit", "credit", "description")
    list_filter = ("account_type", "transaction_date")
    search_fields = ("description", "account_name")
    
    # Strict Read-Only for Ledger
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
