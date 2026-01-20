from rest_framework import serializers
from .models import Invoice, Payment, UtilityBill, Cheque, InvoiceType
from accounting.models import LedgerEntry

class InvoiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceType
        fields = '__all__'

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
    """
    Serializer for creating payments.
    """
    invoice_ref = serializers.CharField(source='invoice.invoice_number', read_only=True)
    cheques = ChequeSerializer(many=True, read_only=True)
    
    # Input for creating a Check
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
    """
    Lighter serializer for list view (no nested heavy objects).
    """
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    unit_name = serializers.CharField(source='contract.unit.unit_number', read_only=True, allow_null=True)
    
    class Meta:
        model = Invoice
        fields = ('id', 'invoice_number', 'invoice_type', 'status', 'issue_date', 'due_date', 'total_amount', 'paid_amount', 'tenant_name', 'unit_name', 'description', 'knowledge_tax_amount', 'knowledge_tax_paid')

class InvoiceSerializer(serializers.ModelSerializer):
    """
    Standard CRUD serializer for Invoices.
    """
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_email = serializers.EmailField(source='tenant.email', read_only=True)
    tenant_phone = serializers.CharField(source='tenant.phone', read_only=True)
    unit_name = serializers.CharField(source='contract.unit.unit_number', read_only=True, allow_null=True)
    
    payments = PaymentSerializer(many=True, read_only=True)
    utility_readings = UtilityBillSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ('status', 'paid_amount', 'invoice_number') # Managed by system
