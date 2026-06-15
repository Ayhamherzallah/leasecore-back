from decimal import Decimal

from rest_framework import serializers
from .models import Invoice, Payment, UtilityBill, Cheque, InvoiceType, InvoiceLineItem
from accounting.models import LedgerEntry


class InvoiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceType
        fields = '__all__'
        extra_kwargs = {'building': {'required': False, 'allow_null': True}}


class InvoiceLineItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceLineItem
        fields = ('id', 'description', 'quantity', 'unit_price', 'line_total', 'sort_order')
        read_only_fields = ('id',)

    def get_line_total(self, obj):
        return obj.line_total


class ChequeSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='payment.invoice.invoice_number', read_only=True)
    tenant_name = serializers.CharField(source='payment.invoice.tenant.name', read_only=True)

    class Meta:
        model = Cheque
        fields = '__all__'


class ChequeInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cheque
        fields = ('cheque_number', 'bank_name', 'drawer_name', 'amount', 'cheque_date', 'cheque_image', 'note')


class PaymentSerializer(serializers.ModelSerializer):
    invoice_ref = serializers.CharField(source='invoice.invoice_number', read_only=True)
    tenant_name = serializers.CharField(source='invoice.tenant.name', read_only=True)
    tenant_id = serializers.IntegerField(source='invoice.tenant.id', read_only=True)
    cheques = ChequeSerializer(many=True, read_only=True)
    cheque_details = ChequeInputSerializer(write_only=True, required=False)

    class Meta:
        model = Payment
        fields = '__all__'

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


class UtilityBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = UtilityBill
        fields = '__all__'


class InvoiceListSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    unit_name = serializers.CharField(source='contract.unit.unit_number', read_only=True, allow_null=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'invoice_number', 'invoice_type', 'status', 'issue_date', 'due_date',
            'total_amount', 'paid_amount', 'tenant_name', 'unit_name', 'description',
            'notes', 'knowledge_tax_amount', 'knowledge_tax_paid',
            'is_overdue', 'days_overdue', 'balance_due',
        )


class InvoiceSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_email = serializers.EmailField(source='tenant.email', read_only=True)
    tenant_phone = serializers.CharField(source='tenant.phone', read_only=True)
    unit_name = serializers.CharField(source='contract.unit.unit_number', read_only=True, allow_null=True)

    payments = PaymentSerializer(many=True, read_only=True)
    utility_readings = UtilityBillSerializer(many=True, read_only=True)
    line_items = InvoiceLineItemSerializer(many=True, required=False)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ('status', 'paid_amount', 'invoice_number', 'total_amount')

    def validate(self, attrs):
        knowledge_tax_amount = attrs.get('knowledge_tax_amount', getattr(self.instance, 'knowledge_tax_amount', 0))
        contract = attrs.get('contract', getattr(self.instance, 'contract', None))

        if knowledge_tax_amount and float(knowledge_tax_amount) > 0 and not contract:
            raise serializers.ValidationError({
                'contract': 'يجب اختيار العقد/الوحدة لفواتير ضريبة المعارف / A contract/unit is required for knowledge tax invoices.'
            })

        line_items = attrs.get('line_items')
        if line_items is not None and len(line_items) == 0:
            raise serializers.ValidationError({'line_items': 'At least one line item is required.'})

        return attrs

    def _save_line_items(self, invoice, items_data):
        invoice.line_items.all().delete()
        for index, item in enumerate(items_data):
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=item['description'],
                quantity=item.get('quantity', Decimal('1')),
                unit_price=item['unit_price'],
                sort_order=item.get('sort_order', index),
            )

    def _subtotal_from_items_data(self, items_data):
        return sum(
            (item.get('quantity') or Decimal('1')) * (item.get('unit_price') or Decimal('0'))
            for item in items_data
        )

    def _recalculate_total(self, invoice):
        subtotal = sum(
            (item.quantity or Decimal('0')) * (item.unit_price or Decimal('0'))
            for item in invoice.line_items.all()
        )
        tax = invoice.knowledge_tax_amount or Decimal('0')
        invoice.total_amount = subtotal + tax
        invoice.save(update_fields=['total_amount', 'updated_at'])

    def _resolve_building(self, validated_data):
        """Owner building: contract's building (authoritative) or the provided one."""
        contract = validated_data.get('contract')
        if contract and contract.unit and contract.unit.floor_id:
            return contract.unit.floor.building
        return validated_data.get('building')

    def create(self, validated_data):
        from users.building_access import user_can_access_building
        from users.utils import is_platform_admin

        line_items_data = validated_data.pop('line_items', None)
        validated_data.pop('total_amount', None)

        if not line_items_data:
            raise serializers.ValidationError({'line_items': 'At least one line item is required.'})

        building = self._resolve_building(validated_data)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not (user and is_platform_admin(user)):
            if building is None or not user_can_access_building(user, building.id):
                raise serializers.ValidationError(
                    {'building': 'A valid building you have access to is required.'}
                )
        validated_data['building'] = building

        tax = validated_data.get('knowledge_tax_amount') or Decimal('0')
        validated_data['total_amount'] = self._subtotal_from_items_data(line_items_data) + tax

        invoice = Invoice.objects.create(**validated_data)
        self._save_line_items(invoice, line_items_data)
        return invoice

    def update(self, instance, validated_data):
        if instance.status != Invoice.InvoiceStatus.DRAFT:
            raise serializers.ValidationError({'status': 'Only draft invoices can be edited.'})

        line_items_data = validated_data.pop('line_items', None)
        validated_data.pop('total_amount', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Keep the owner building aligned with the contract when present.
        if instance.contract and instance.contract.unit and instance.contract.unit.floor_id:
            instance.building = instance.contract.unit.floor.building
        instance.save()

        if line_items_data is not None:
            self._save_line_items(instance, line_items_data)
            self._recalculate_total(instance)

        return instance
