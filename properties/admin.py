from django.contrib import admin
from .models import Building, Floor, Unit

@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "total_area")
    search_fields = ("name", "address")

@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("name", "number", "building")
    list_filter = ("building",)

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    # FIXED: Refers to actual model fields or methods decorated with @admin.display
    list_display = ("unit_number", "floor", "market_rent", "status", "get_current_contract_display")
    list_filter = ("floor__building", "status") # FIXED: 'is_occupied' was not a field, used 'status'
    search_fields = ("unit_number",)

    @admin.display(description="Current Contract")
    def get_current_contract_display(self, obj):
        # Determine current contract via reverse relation
        # contracts is related_name from tenant.Contract.unit
        active_contract = obj.contracts.filter(status='ACTIVE').first()
        return active_contract if active_contract else "Vacant"
