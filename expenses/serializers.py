from rest_framework import serializers
from .models import Expense, ExpenseCategory

class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'description']

class ExpenseSerializer(serializers.ModelSerializer):
    category_details = ExpenseCategorySerializer(source='category', read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects.all())

    class Meta:
        model = Expense
        fields = '__all__'
        
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Expense amount must be positive.")
        return value
