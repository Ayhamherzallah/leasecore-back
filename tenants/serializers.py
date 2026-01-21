from rest_framework import serializers
from .models import Tenant, Contract, TenantDocument

class TenantDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantDocument
        fields = ['id', 'document', 'description', 'created_at']


class TenantLiteSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for dropdowns/selects.
    No financial calculations = very fast.
    """
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'phone', 'tenant_type']


class TenantSerializer(serializers.ModelSerializer):
    """
    Full serializer with financial stats pre-calculated via annotations.
    """
    documents = TenantDocumentSerializer(many=True, read_only=True)
    
    # These come from annotations in the ViewSet queryset
    total_invoiced = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outstanding = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    contract_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tenant
        fields = ['id', 'name', 'national_id', 'tax_number', 'email', 'phone', 'tenant_type', 
                  'documents', 'total_invoiced', 'total_paid', 'outstanding', 'contract_count']

class ContractSerializer(serializers.ModelSerializer):
    # Direct lookups via select_related (fast)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_phone = serializers.CharField(source='tenant.phone', read_only=True)
    unit_number = serializers.CharField(source='unit.unit_number', read_only=True)
    unit_floor = serializers.CharField(source='unit.floor.name', read_only=True)
    
    # Pre-calculated via annotations in the ViewSet (fast)
    invoice_count = serializers.IntegerField(read_only=True)
    total_invoiced = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Contract
        fields = '__all__'
