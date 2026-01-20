from decimal import Decimal
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from .models import LedgerEntry

class AccountingService:
    """
    Central Service for all Double-Entry Accounting Operations.
    Ensures that every financial event creates balanced ledger entries.
    Strict Idempotency: Never double-book.
    
    UPDATED: Uses Cash-Basis Revenue Recognition.
    Invoices book to Unearned Revenue (Liability).
    Payments book to Realized Revenue (Income).
    """

    @staticmethod
    def _entries_exist(source_obj):
        """Check if ledger entries already exist for source object."""
        c_type = ContentType.objects.get_for_model(source_obj)
        return LedgerEntry.objects.filter(content_type=c_type, object_id=source_obj.id).exists()

    @staticmethod
    def revert_entries(source_obj):
        """Hard delete ledger entries for a source object. Use for error correction."""
        c_type = ContentType.objects.get_for_model(source_obj)
        LedgerEntry.objects.filter(content_type=c_type, object_id=source_obj.id).delete()


    @staticmethod
    def _create_entry(building, transaction_date, description, source_obj, entries):
        """
        Internal Traceable Entry Creator.
        'entries' should be a list of dicts: {'account': str, 'type': str, 'debit': Decimal, 'credit': Decimal}
        """
        # sanity check: debits must equal credits
        total_debit = sum(e['debit'] for e in entries)
        total_credit = sum(e['credit'] for e in entries)
        
        # Round to 2 decimal places to minimize float issues, though Decimals should be fine
        total_debit = round(total_debit, 2)
        total_credit = round(total_credit, 2)

        if total_debit != total_credit:
            raise ValueError(f"Accounting Error: Unbalanced Transaction. Dr: {total_debit}, Cr: {total_credit}")

        ledger_records = []
        for entry in entries:
            ledger_records.append(LedgerEntry(
                building=building,
                transaction_date=transaction_date,
                description=description,
                source_object=source_obj, # GenericForeignKey magic
                account_name=entry['account'],
                account_type=entry['type'],
                debit=entry['debit'],
                credit=entry['credit']
            ))
        
        # Bulk Create for Atomicity
        LedgerEntry.objects.bulk_create(ledger_records)

    @classmethod
    @transaction.atomic
    def process_invoice_ledger(cls, invoice):
        """
        Invoked by Billing Service when an invoice is formally ISSUED.
        Books AR vs Unearned Revenue (Liability).
        """
        if cls._entries_exist(invoice):
            return # Idempotency check: Already booked.

        # Building Context - with fallback for invoices without contracts (e.g., Knowledge Tax)
        building = None
        if invoice.contract and invoice.contract.unit:
            building = invoice.contract.unit.floor.building
        else:
            # Fallback 1: Try to get building from tenant's active contract
            from tenants.models import Contract
            active_contract = Contract.objects.filter(
                tenant=invoice.tenant, 
                status='ACTIVE'
            ).select_related('unit__floor__building').first()
            
            if active_contract and active_contract.unit:
                building = active_contract.unit.floor.building
            else:
                # Fallback 2: Use the first building in the system
                from properties.models import Building
                building = Building.objects.first()
                
            if not building:
                raise ValueError(f"Accounting Error: Invoice {invoice.invoice_number} has no linked Contract and no fallback Building found.")
        
        # In Cash Basis model, issuance is: Dr AR, Cr Unearned Revenue (Liability)
        # We do NOT book Income yet.
        
        entries = [
            {
                'account': "Accounts Receivable",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': invoice.total_amount,
                'credit': Decimal('0.00')
            },
            {
                'account': "Unearned Revenue",
                'type': LedgerEntry.AccountType.LIABILITY,
                'debit': Decimal('0.00'),
                'credit': invoice.total_amount
            }
        ]
        
        cls._create_entry(
            building=building,
            transaction_date=invoice.issue_date,
            description=f"فاتورة صادرة: {invoice.invoice_number}",
            source_obj=invoice,
            entries=entries
        )

    @classmethod
    @transaction.atomic
    def process_payment_ledger(cls, payment):
        """
        Invoked by Billing Service when a payment is RECEIVED.
        1. Current Asset Move: Dr Bank / Cr AR
        2. Revenue Recognition: Dr Unearned Revenue / Cr Realized Income
        """
        if cls._entries_exist(payment):
            return # Idempotency check

        invoice = payment.invoice
        # Building context - with fallback for invoices without contracts
        building = None
        if invoice.contract and invoice.contract.unit:
            building = invoice.contract.unit.floor.building
        else:
            # Fallback 1: Try to get building from tenant's active contract
            from tenants.models import Contract
            active_contract = Contract.objects.filter(
                tenant=invoice.tenant, 
                status='ACTIVE'
            ).select_related('unit__floor__building').first()
            
            if active_contract and active_contract.unit:
                building = active_contract.unit.floor.building
            else:
                # Fallback 2: Use the first building in the system
                from properties.models import Building
                building = Building.objects.first()
                
            if not building:
                raise ValueError(f"Accounting Error: Payment for Invoice {invoice.invoice_number} has no linked Contract and no fallback Building found.")

        # Determine Specific Revenue Account based on Invoice Type
        revenue_account = "Rental Income"
        if invoice.invoice_type == "UTILITY":
            revenue_account = "Utility Income"
        elif invoice.invoice_type == "SERVICE":
            revenue_account = "Service Income"
        elif invoice.invoice_type == "PENALTY":
            revenue_account = "Other Income"

        entries = [
            # 1. Asset Move
            {
                'account': "PDC In Hand" if payment.payment_method == 'CHECK' else "Bank / Cash", 
                'type': LedgerEntry.AccountType.ASSET,
                'debit': payment.amount,
                'credit': Decimal('0.00')
            },
            {
                'account': "Accounts Receivable",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': Decimal('0.00'),
                'credit': payment.amount
            }
        ]

        # 2. Revenue Recognition
        # RULE: If Payment is CHEQUE (PDC), do NOT recognize revenue yet. 
        # Revenue is recognized only upon Clearance (Cash Realization).
        if payment.payment_method != 'CHECK':
            entries.extend([
                {
                    'account': "Unearned Revenue",
                    'type': LedgerEntry.AccountType.LIABILITY,
                    'debit': payment.amount,
                    'credit': Decimal('0.00')
                },
                {
                    'account': revenue_account,
                    'type': LedgerEntry.AccountType.REVENUE,
                    'debit': Decimal('0.00'),
                    'credit': payment.amount
                }
            ])

        ref_display = payment.reference_number if payment.reference_number else f"#{payment.id}"
        
        cls._create_entry(
            building=building,
            transaction_date=payment.payment_date,
            description=f"دفعة مستلمة ({'شيك' if payment.payment_method == 'CHECK' else 'نقد/تحويل'}): {ref_display}",
            source_obj=payment,
            entries=entries
        )

    @classmethod
    @transaction.atomic
    def process_cheque_clearance(cls, cheque):
        """
        Invoked when a PDC is marked as CLEARED.
        1. Money moves from PDC In Hand -> Bank.
        2. Revenue is RECOGNIZED (Dr Unearned, Cr Income).
        """
        payment = cheque.payment
        invoice = payment.invoice
        
        # Building context - with fallback
        building = None
        if invoice.contract and invoice.contract.unit:
            building = invoice.contract.unit.floor.building
        else:
            from tenants.models import Contract
            active_contract = Contract.objects.filter(
                tenant=invoice.tenant, 
                status='ACTIVE'
            ).select_related('unit__floor__building').first()
            
            if active_contract and active_contract.unit:
                building = active_contract.unit.floor.building
            else:
                from properties.models import Building
                building = Building.objects.first()
        
        # Determine Revenue Account
        revenue_account = "Rental Income"
        if invoice.invoice_type == "UTILITY": revenue_account = "Utility Income"
        elif invoice.invoice_type == "SERVICE": revenue_account = "Service Income"
        elif invoice.invoice_type == "PENALTY": revenue_account = "Other Income"

        entries = [
            # 1. Move Asset: PDC -> Bank
            {
                'account': "Bank / Cash",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': cheque.amount,
                'credit': Decimal('0.00')
            },
            {
                'account': "PDC In Hand",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': Decimal('0.00'),
                'credit': cheque.amount
            },
            # 2. Recognize Revenue
            {
                'account': "Unearned Revenue",
                'type': LedgerEntry.AccountType.LIABILITY,
                'debit': cheque.amount,
                'credit': Decimal('0.00')
            },
            {
                'account': revenue_account,
                'type': LedgerEntry.AccountType.REVENUE,
                'debit': Decimal('0.00'),
                'credit': cheque.amount
            }
        ]

        cls._create_entry(
            building=building,
            transaction_date=cheque.cleared_date or cheque.cheque_date,
            description=f"تحصيل شيك: {cheque.cheque_number}",
            source_obj=cheque,
            entries=entries
        )

    @classmethod
    @transaction.atomic
    def process_cheque_bounce(cls, cheque):
        """
        Invoked when a PDC BOUNCES.
        1. Reverses the receipt: Dr AR, Cr PDC In Hand.
        The Debt is effectively reinstated.
        """
        payment = cheque.payment
        invoice = payment.invoice
        
        # Building context - with fallback
        building = None
        if invoice.contract and invoice.contract.unit:
            building = invoice.contract.unit.floor.building
        else:
            from tenants.models import Contract
            active_contract = Contract.objects.filter(
                tenant=invoice.tenant, 
                status='ACTIVE'
            ).select_related('unit__floor__building').first()
            
            if active_contract and active_contract.unit:
                building = active_contract.unit.floor.building
            else:
                from properties.models import Building
                building = Building.objects.first()

        entries = [
            # Reverse the initial receipt
            {
                'account': "Accounts Receivable",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': cheque.amount,
                'credit': Decimal('0.00')
            },
            {
                'account': "PDC In Hand",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': Decimal('0.00'),
                'credit': cheque.amount
            }
        ]

        cls._create_entry(
            building=building,
            transaction_date=cheque.bounced_date or cheque.cheque_date,
            description=f"شيك مرتجع: {cheque.cheque_number}",
            source_obj=cheque,
            entries=entries
        )

    @classmethod
    @transaction.atomic
    def process_expense_ledger(cls, expense):
        """
        Invoked by Expense Service when expense is RECORDED.
        Books Expense vs Bank (Cash Basis).
        """
        if cls._entries_exist(expense):
            return # Idempotency check

        entries = [
            {
                'account': expense.category.name,  # Dynamic category name
                'type': LedgerEntry.AccountType.EXPENSE,
                'debit': expense.amount,
                'credit': Decimal('0.00')
            },
            {
                'account': "Bank / Cash",
                'type': LedgerEntry.AccountType.ASSET,
                'debit': Decimal('0.00'),
                'credit': expense.amount
            }
        ]

        cls._create_entry(
            building=expense.building,
            transaction_date=expense.expense_date,
            description=f"مصروف: {expense.description}",
            source_obj=expense,
            entries=entries
        )
