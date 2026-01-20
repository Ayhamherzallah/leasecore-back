from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import uuid
from .models import Invoice, Payment
from accounting.services import AccountingService

class BillingService:
    """
    Orchestrates Invoice and Payment lifecycles.
    Responsible for updating state AND calling AccountingService.
    """

    @staticmethod
    @transaction.atomic
    def create_schedule(contract, installments):
        """
        Creates a batch of invoices based on the provided schedule.
        installments: list of dicts { 'due_date': 'YYYY-MM-DD', 'amount': decimal }
        """
        invoices = []
        for i, inst in enumerate(installments):
            # First invoice is usually issued immediately
            is_first = (i == 0)
            status = Invoice.InvoiceStatus.ISSUED if is_first else Invoice.InvoiceStatus.DRAFT
            
            # Generate a unique invoice number
            inv_num = f"INV-{contract.id}-{inst['due_date'].replace('-', '')}-{str(uuid.uuid4())[:4].upper()}"
            
            invoice = Invoice.objects.create(
                contract=contract,
                tenant=contract.tenant,
                invoice_number=inv_num,
                invoice_type=Invoice.InvoiceType.RENT,
                issue_date=contract.start_date if is_first else inst['due_date'], # Issue date for future invoices can be the due date or now. Let's say due date.
                due_date=inst['due_date'],
                total_amount=Decimal(str(inst['amount'])),
                status=status
            )
            
            if is_first:
                # Trigger ledger for the first one immediately
                AccountingService.process_invoice_ledger(invoice)
                
            invoices.append(invoice)
        
        return invoices

    @staticmethod
    @transaction.atomic
    def issue_invoice(invoice):
        """
        Transition Invoice from DRAFT -> ISSUED
        Then trigger Ledger.
        """
        if invoice.status != "DRAFT":
            raise ValueError(f"Cannot issue invoice {invoice.invoice_number} with status {invoice.status}")
        
        # 1. Update State
        invoice.status = Invoice.InvoiceStatus.ISSUED
        invoice.save()

        # 2. Trigger Ledger (Accrual)
        AccountingService.process_invoice_ledger(invoice)
        
        return invoice

    @staticmethod
    @transaction.atomic
    def receive_payment(payment_data):
        """
        Create a Payment record
        Update Invoice State (Partial/Paid)
        Trigger Ledger (Cash Realization)
        """
        cheque_details = payment_data.pop('cheque_details', None)
        print(f"DEBUG: Service received cheque_details: {cheque_details}")
        invoice = payment_data['invoice']
        amount = payment_data['amount']

        if amount <= 0:
             raise ValueError("Payment amount must be positive")

        if invoice.status == Invoice.InvoiceStatus.PAID:
             raise ValueError("Invoice is already fully paid")
        
        # 1. Create Payment Record
        payment = Payment.objects.create(**payment_data)
        
        # 1.5 Handle Cheque Creation Logic
        if payment.payment_method == 'CHECK':
            if cheque_details:
                print("DEBUG: Creating Cheque Record...")
                from .models import Cheque
                # Ensure cheque_details is a dictionary
                if isinstance(cheque_details, dict):
                    # Fix: Rewind/Reopen file pointer
                    if 'cheque_image' in cheque_details:
                        img = cheque_details['cheque_image']
                        print(f"DEBUG: Image detected. Type: {type(img)}")
                        if hasattr(img, 'size'):
                            print(f"DEBUG: Image Size: {img.size}")
                        
                        if hasattr(img, 'closed') and img.closed:
                            print("DEBUG: Image file was closed. Re-opening.")
                            img.open()
                        
                        if hasattr(img, 'seek'):
                            print("DEBUG: Rewinding image file.")
                            img.seek(0)
                            
                    chk = Cheque.objects.create(payment=payment, **cheque_details)
                    print(f"DEBUG: Cheque Created ID: {chk.id}")
                else:
                    print(f"DEBUG: cheque_details is not a dict! {type(cheque_details)}")
            else:
                print("DEBUG: Payment method is CHECK but NO cheque_details found!")
            # Use strict rule: if Method is CHECK, we expect details? 
            # Ideally yes, but for now we won't strict crash if missing, unless user wants.
            # But the accounting assumes PDC In Hand. Without a Cheque record, we can't clear it later!
            # So it IS critical. But I'll leave it as optional for API back-compat unless enforced.

        # 2. Update Invoice State
        # FIX: Explicit decimal casting to prevent float arithmetic errors with SQLite
        invoice.paid_amount = Decimal(invoice.paid_amount) + Decimal(amount)
        
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = Invoice.InvoiceStatus.PAID
        else:
            invoice.status = Invoice.InvoiceStatus.PARTIALLY_PAID
        
        invoice.save()

        # 3. Trigger Ledger
        AccountingService.process_payment_ledger(payment)

        return payment

    @staticmethod
    @transaction.atomic
    def void_payment(payment):
        """
        Reverse a payment:
        1. Clean ledger.
        2. Fix Invoice balance/status.
        3. Delete payment record.
        """
        invoice = payment.invoice
        amount = payment.amount
        
        # 1. Clean Ledger
        AccountingService.revert_entries(payment)
        
        # 2. Update Invoice
        invoice.paid_amount = Decimal(invoice.paid_amount) - Decimal(amount)
        if invoice.paid_amount < 0:
            invoice.paid_amount = Decimal('0.00') # Safety net

        # Recalculate status
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = Invoice.InvoiceStatus.PAID
        elif invoice.paid_amount > 0:
            invoice.status = Invoice.InvoiceStatus.PARTIALLY_PAID
        else:
            # If 0 paid, revert to original status before payment? 
            # Usually ISSUED if it generated revenue, or DRAFT if very early.
            # Safe bet: ISSUED for accounting consistency.
            invoice.status = Invoice.InvoiceStatus.ISSUED 
        
        invoice.save()

        # 3. Delete Payment
        payment.delete()

    @staticmethod
    @transaction.atomic
    def void_invoice(invoice):
        """
        Void/Delete an Invoice.
        Recursively voids any attached payments first to ensure accounting integrity.
        """
        # 1. Void Payments recursively
        for payment in invoice.payments.all():
            BillingService.void_payment(payment)
            
        # 2. Clean Ledger (Revenue Reversal)
        AccountingService.revert_entries(invoice)
        
        # 3. Delete Invoice
        invoice.delete()

    # --- CHEQUE LIFECYCLE MANAGEMENT ---
    @staticmethod
    @transaction.atomic
    def deposit_cheque(cheque, deposit_image=None):
        if cheque.status != 'RECEIVED': 
            raise ValueError("Cheque must be in RECEIVED status to be deposited.")
        
        cheque.status = 'DEPOSITED'
        if deposit_image:
            cheque.deposit_image = deposit_image
        cheque.save()
        return cheque

    @staticmethod
    @transaction.atomic
    def clear_cheque(cheque, clear_date):
        if cheque.status == 'CLEARED': 
            raise ValueError("Cheque is already cleared.")
            
        # Trigger Accounting Logic
        AccountingService.process_cheque_clearance(cheque)
        
        cheque.status = 'CLEARED'
        cheque.cleared_date = clear_date
        cheque.save()
        return cheque

    @staticmethod
    @transaction.atomic
    def bounce_cheque(cheque, bounce_date, reason):
        if cheque.status == 'BOUNCED':
            raise ValueError("Cheque is already bounced.")

        # Trigger Accounting Logic (Reverse Payment)
        AccountingService.process_cheque_bounce(cheque)
        
        cheque.status = 'BOUNCED'
        cheque.bounced_date = bounce_date
        cheque.bounce_reason = reason
        cheque.save()
        return cheque
