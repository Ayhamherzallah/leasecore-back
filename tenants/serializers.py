from rest_framework import serializers
from .models import Tenant, Contract

class TenantSerializer(serializers.ModelSerializer):
    financial_stats = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = ['id', 'name', 'national_id', 'email', 'phone', 'tenant_type', 'financial_stats']

    def get_financial_stats(self, obj):
        from billing.models import Invoice
        from django.db.models import Sum
        
        invoices = Invoice.objects.filter(tenant=obj)
        total_invoiced = invoices.aggregate(s=Sum('total_amount'))['s'] or 0
        total_paid = invoices.aggregate(s=Sum('paid_amount'))['s'] or 0
        
        return {
            'total_invoiced': total_invoiced,
            'total_paid': total_paid,
            'outstanding': total_invoiced - total_paid,
            'payment_ratio': (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0
        }

class ContractSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contract
        fields = '__all__'
