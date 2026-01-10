from django.contrib import admin
from .models import Expense

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    # Fixed: Removed 'paid_by' which is not in the model
    list_display = ("description", "building", "category", "amount", "expense_date") 
    list_filter = ("category", "expense_date", "building")
    search_fields = ("description",)
