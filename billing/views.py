from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import io
from django_filters.rest_framework import DjangoFilterBackend
from .models import Invoice, Payment, Cheque
from .serializers import InvoiceSerializer, PaymentSerializer, ChequeSerializer
from .services import BillingService
from .pdf import generate_invoice_pdf, generate_receipt_pdf
from users.permissions import CanPerformFinancialCommand

class ChequeViewSet(viewsets.ModelViewSet):
    """
    Manage Cheques (PDCs).
    Supports:
    - List/Filter
    - Actions: deposit, clear, bounce
    """
    queryset = Cheque.objects.all().order_by('cheque_date')
    serializer_class = ChequeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'cheque_date', 'payment__invoice__tenant']
    permission_classes = [CanPerformFinancialCommand]

    @action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        cheque = self.get_object()
        try:
            BillingService.deposit_cheque(cheque)
            return Response(self.get_serializer(cheque).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def clear(self, request, pk=None):
        cheque = self.get_object()
        date_str = request.data.get('date')
        try:
            BillingService.clear_cheque(cheque, date_str)
            return Response(self.get_serializer(cheque).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def bounce(self, request, pk=None):
        cheque = self.get_object()
        date_str = request.data.get('date')
        reason = request.data.get('reason', 'Insufficient Funds')
        try:
            # If no date provided, use today in service (but service expects arg)
            # Service expects valid date or None? Service logic: `bounce_date`.
            # If None, use Today. I'll let View handle it or Service. Service didn't default it.
            # I'll default here.
            from datetime import date
            if not date_str: date_str = date.today()
            
            BillingService.bounce_cheque(cheque, date_str, reason)
            return Response(self.get_serializer(cheque).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class InvoiceViewSet(viewsets.ModelViewSet):
    """
    Invoices Management.
    Supports:
    - GET (List/Retrieve)
    - DELETE (Void/Reverse Accounting)
    - PUT/PATCH (Update dates/details)
    """
    queryset = Invoice.objects.all().order_by('-issue_date', '-id')
    serializer_class = InvoiceSerializer
    permission_classes = [CanPerformFinancialCommand]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'contract', 'invoice_number']

    def perform_destroy(self, instance):
        """
        Custom Destroy: Delegate to Service to clean up Ledger & Payments.
        """
        BillingService.void_invoice(instance)

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """
        POST /api/billing/invoices/{id}/issue/
        Triggers BillingService.issue_invoice()
        """
        invoice = self.get_object()
        try:
            # Delegate to Service
            updated_invoice = BillingService.issue_invoice(invoice)
            serializer = self.get_serializer(updated_invoice)
            return Response(serializer.data)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """
        GET /api/billing/invoices/{id}/pdf/
        Generates PDF.
        """
        invoice = self.get_object()
        buffer = generate_invoice_pdf(invoice)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
        return response

class PaymentViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """
    Payments Management.
    Supports:
    - GET (List/Retrieve)
    - POST (Record Payment)
    - DELETE (Void/Reverse Payment)
    """
    queryset = Payment.objects.all().order_by('-payment_date', '-id')
    serializer_class = PaymentSerializer
    permission_classes = [CanPerformFinancialCommand]
    filter_backends = [DjangoFilterBackend]
    # Note: 'invoice__tenant' requires related filter setup, typically automatic with django-filters
    # but exact lookup might need explicit declaring if strictly matching ID.
    filterset_fields = ['invoice', 'invoice__tenant', 'payment_date', 'payment_method', 'reference_number']

    def perform_destroy(self, instance):
        """
        Custom Destroy: Delegate to Service to reverse accounting & balance.
        """
        BillingService.void_payment(instance)

    def create(self, request, *args, **kwargs):
        """
        POST /api/billing/payments/
        Strict delegation to BillingService.receive_payment
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract validated data
        payment_data = {**serializer.validated_data}

        try:
            # Delegate to Service
            payment = BillingService.receive_payment(payment_data)
            # Re-serialize for response
            response_serializer = self.get_serializer(payment)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """
        GET /api/billing/payments/{id}/pdf/
        Generates Receipt PDF.
        """
        payment = self.get_object()
        buffer = generate_receipt_pdf(payment)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Receipt_{payment.id}.pdf"'
        return response
