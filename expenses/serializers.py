from rest_framework import serializers
from .models import Expense, ExpenseCategory

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'description']

class ExpenseSerializer(serializers.ModelSerializer):
    category_details = ExpenseCategorySerializer(source='category', read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects.all())
    
    # Helpers
    category_name = serializers.CharField(source='category.name', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_number', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)

    class Meta:
        model = Expense
        fields = '__all__'
        
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Expense amount must be positive.")
        return value
