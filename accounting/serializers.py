from rest_framework import serializers
from .models import LedgerEntry

class LedgerEntrySerializer(serializers.ModelSerializer):
    """
    Read-Only Ledger View.
    """
    source_type = serializers.CharField(source='content_type.model', read_only=True)
    source_id = serializers.IntegerField(source='object_id', read_only=True)

    class Meta:
        model = LedgerEntry
        fields = [
            'id', 'transaction_date', 'account_name', 'account_type',
            'debit', 'credit', 'description', 'source_type', 'source_id'
        ]
