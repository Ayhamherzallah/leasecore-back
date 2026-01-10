from rest_framework import serializers
from .models import Building, Floor, Unit

class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'address', 'total_area']

class FloorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Floor
        fields = ['id', 'name', 'number', 'building']

class UnitSerializer(serializers.ModelSerializer):
    active_contract = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = ['id', 'unit_number', 'unit_type', 'status', 'area', 'market_rent', 'floor', 'active_contract']

    def get_active_contract(self, obj):
        # Return full details of the active contract if exists
        try:
            # Avoid circular import issues by importing here if necessary, 
            # though standard imports usually work if models are loaded.
            # Using reverse relation 'contracts'
            contract = obj.contracts.filter(status='ACTIVE').select_related('tenant').first()
            if contract:
                # Calculate Total Paid
                # We need to import Sum here or at top level. 
                # Doing concise import to avoid conflicts if not present.
                from django.db.models import Sum
                total_paid = contract.invoices.aggregate(total=Sum('paid_amount'))['total'] or 0.00
                
                # Calculate Next Payment Due (Earliest Unpaid/Partial Invoice)
                # Invoice status choice 'PAID' or simply total_amount > paid_amount
                next_invoice = contract.invoices.exclude(status='PAID').order_by('due_date').first()
                if next_invoice:
                    next_payment_date = next_invoice.due_date
                elif not contract.invoices.exists():
                    # No invoices yet, so next payment is the start of the contract
                    next_payment_date = contract.start_date
                else:
                    # Invoices exist but all are paid
                    next_payment_date = None
                
                return {
                    "id": contract.id,
                    "start_date": contract.start_date,
                    "end_date": contract.end_date,
                    "rent_amount": contract.rent_amount,
                    "payment_frequency": contract.payment_frequency,
                    "security_deposit": contract.security_deposit,
                    "total_paid": total_paid,
                    "next_payment_date": next_payment_date,
                    "tenant": {
                        "id": contract.tenant.id,
                        "name": contract.tenant.name,
                        "email": contract.tenant.email,
                        "phone": contract.tenant.phone,
                        "national_id": contract.tenant.national_id,
                        "type": contract.tenant.tenant_type
                    }
                }
        except Exception:
            return None
        return None
