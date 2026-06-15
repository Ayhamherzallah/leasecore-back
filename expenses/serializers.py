from rest_framework import serializers
from .models import Expense, ExpenseCategory, FixedCost, FixedCostOccurrence
from .services import FixedCostService


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'description', 'building']
        extra_kwargs = {'building': {'required': False, 'allow_null': True}}


class ExpenseSerializer(serializers.ModelSerializer):
    category_details = ExpenseCategorySerializer(source='category', read_only=True)
    category = serializers.PrimaryKeyRelatedField(queryset=ExpenseCategory.objects.all())

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


class FixedCostOccurrenceSerializer(serializers.ModelSerializer):
    fixed_cost_name = serializers.CharField(source='fixed_cost.name', read_only=True)
    category_name = serializers.CharField(source='fixed_cost.category.name', read_only=True)
    building_name = serializers.CharField(source='fixed_cost.building.name', read_only=True)
    vendor_name = serializers.CharField(source='fixed_cost.vendor_name', read_only=True)
    frequency = serializers.CharField(source='fixed_cost.frequency', read_only=True)

    class Meta:
        model = FixedCostOccurrence
        fields = [
            'id', 'fixed_cost', 'fixed_cost_name', 'category_name', 'building_name',
            'vendor_name', 'frequency', 'period_date', 'amount', 'status',
            'expense', 'confirmed_at', 'created_at',
        ]
        read_only_fields = fields


class FixedCostSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    building_name = serializers.CharField(source='building.name', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_number', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)

    pending_count = serializers.SerializerMethodField()
    confirmed_count = serializers.SerializerMethodField()
    next_due_date = serializers.SerializerMethodField()
    monthly_equivalent = serializers.SerializerMethodField()

    class Meta:
        model = FixedCost
        fields = [
            'id', 'building', 'building_name', 'category', 'category_name',
            'unit', 'unit_name', 'name', 'vendor_name', 'notes', 'amount',
            'frequency', 'frequency_display', 'custom_interval', 'custom_unit',
            'start_date', 'end_date', 'is_active',
            'pending_count', 'confirmed_count', 'next_due_date', 'monthly_equivalent',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_pending_count(self, obj):
        return obj.occurrences.filter(status=FixedCostOccurrence.Status.PENDING).count()

    def get_confirmed_count(self, obj):
        return obj.occurrences.filter(status=FixedCostOccurrence.Status.CONFIRMED).count()

    def get_next_due_date(self, obj):
        """The next period date that hasn't been materialised yet."""
        last = obj.occurrences.order_by('-period_date').first()
        nxt = FixedCostService._step(obj, last.period_date) if last else obj.start_date
        if obj.end_date and nxt > obj.end_date:
            return None
        return nxt

    def get_monthly_equivalent(self, obj):
        """Approximate monthly cost for dashboards/totals."""
        amt = float(obj.amount)
        factor = {
            FixedCost.Frequency.WEEKLY: 52 / 12,
            FixedCost.Frequency.MONTHLY: 1,
            FixedCost.Frequency.QUARTERLY: 1 / 3,
            FixedCost.Frequency.SEMIANNUAL: 1 / 6,
            FixedCost.Frequency.YEARLY: 1 / 12,
        }.get(obj.frequency)
        if factor is None:  # CUSTOM
            interval = obj.custom_interval or 1
            unit = obj.custom_unit or FixedCost.CustomUnit.MONTH
            if unit == FixedCost.CustomUnit.DAY:
                factor = 30 / interval
            elif unit == FixedCost.CustomUnit.WEEK:
                factor = (52 / 12) / interval
            else:
                factor = 1 / interval
        return round(amt * factor, 2)

    def validate(self, data):
        freq = data.get('frequency', getattr(self.instance, 'frequency', None))
        if freq == FixedCost.Frequency.CUSTOM:
            interval = data.get('custom_interval', getattr(self.instance, 'custom_interval', None))
            unit = data.get('custom_unit', getattr(self.instance, 'custom_unit', None))
            if not interval or not unit:
                raise serializers.ValidationError(
                    {'custom_interval': 'Custom interval and unit are required for a custom frequency.'}
                )
        end = data.get('end_date', getattr(self.instance, 'end_date', None))
        start = data.get('start_date', getattr(self.instance, 'start_date', None))
        if end and start and end < start:
            raise serializers.ValidationError({'end_date': 'End date cannot be before start date.'})
        return data

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
