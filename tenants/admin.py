from django.contrib import admin
from .models import Tenant, Contract

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant_type", "national_id", "email", "phone")
    search_fields = ("name", "national_id", "email", "phone")
    list_filter = ("tenant_type",)

@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "unit", "start_date", "end_date", "rent_amount", "status")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("tenant__name", "unit__unit_number")
    autocomplete_fields = ["tenant", "unit"]
