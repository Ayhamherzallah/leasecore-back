from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
import io
from django_filters.rest_framework import DjangoFilterBackend
from .models import Invoice, Payment, Cheque, InvoiceType
from .serializers import InvoiceSerializer, InvoiceListSerializer, PaymentSerializer, ChequeSerializer, InvoiceTypeSerializer
from .services import BillingService
from .pdf import generate_invoice_pdf, generate_receipt_pdf
from rest_framework.exceptions import PermissionDenied, ValidationError
from users.permissions import CanPerformFinancialCommand
from users.building_access import scope_invoices, scope_payments, scope_cheques, scope_catalog, user_can_access_building
from users.utils import is_platform_admin

class InvoiceTypeViewSet(viewsets.ModelViewSet):
    queryset = InvoiceType.objects.all().order_by('name')
    serializer_class = InvoiceTypeSerializer
    permission_classes = [CanPerformFinancialCommand]

    def get_queryset(self):
        return scope_catalog(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        building = serializer.validated_data.get('building')
        user = self.request.user
        if not is_platform_admin(user):
            if building is None or not user_can_access_building(user, building.id):
                raise ValidationError({'building': 'A valid building you have access to is required.'})
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.building_id is None and not is_platform_admin(self.request.user):
            raise PermissionDenied('System default types cannot be modified.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.building_id is None and not is_platform_admin(self.request.user):
            raise PermissionDenied('System default types cannot be deleted.')
        instance.delete()

class ChequeViewSet(viewsets.ModelViewSet):
    """
    Manage Cheques (PDCs).
    Supports:
    - List/Filter
    - Actions: deposit, clear, bounce
    Optimized with select_related for fast loading.
    """
    queryset = Cheque.objects.select_related(
        'payment',
        'payment__invoice',
        'payment__invoice__tenant'
    ).all().order_by('cheque_date')
    serializer_class = ChequeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'cheque_date', 'payment__invoice__tenant']
    permission_classes = [CanPerformFinancialCommand]

    def get_queryset(self):
        return scope_cheques(super().get_queryset(), self.request.user)

    @action(detail=True, methods=['post'])
    def deposit(self, request, pk=None):
        cheque = self.get_object()
        deposit_image = request.FILES.get('deposit_image')
        try:
            BillingService.deposit_cheque(cheque, deposit_image=deposit_image)
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
    queryset = Invoice.objects.select_related(
        'tenant', 'contract', 'contract__unit'
    ).prefetch_related('line_items').all().order_by('-issue_date', '-id')
    permission_classes = [CanPerformFinancialCommand]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'status', 'contract', 'invoice_number', 'invoice_type']

    def get_queryset(self):
        return scope_invoices(super().get_queryset(), self.request.user)

    def get_serializer_class(self):
        if self.action in ('list', 'notifications'):
            return InvoiceListSerializer
        return InvoiceSerializer

    @action(detail=False, methods=['get'])
    def notifications(self, request):
        """
        GET /api/billing/invoices/notifications/
        Overdue invoices (issued/partially-paid, past due date, balance > 0)
        scoped to the user's buildings — used for the alerts bell and badges.
        """
        from django.utils import timezone
        from django.db.models import F, Sum

        today = timezone.now().date()
        overdue_qs = self.get_queryset().filter(
            status__in=[
                Invoice.InvoiceStatus.ISSUED,
                Invoice.InvoiceStatus.PARTIALLY_PAID,
                Invoice.InvoiceStatus.OVERDUE,
            ],
            due_date__lt=today,
        ).annotate(
            _balance=F('total_amount') - F('paid_amount')
        ).filter(_balance__gt=0).order_by('due_date')

        agg = overdue_qs.aggregate(total=Sum('_balance'))
        serializer = self.get_serializer(overdue_qs[:50], many=True)
        return Response({
            'count': overdue_qs.count(),
            'total_amount': float(agg['total'] or 0),
            'results': serializer.data,
        })

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
        lang = request.query_params.get('lang', 'en')
        buffer = generate_invoice_pdf(invoice, lang=lang)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_number}.pdf"'
        return response

    @action(detail=True, methods=['post'])
    def mark_knowledge_tax_paid(self, request, pk=None):
        """
        POST /api/billing/invoices/{id}/mark_knowledge_tax_paid/
        Mark the knowledge tax as paid to municipality.
        """
        invoice = self.get_object()
        from django.utils import timezone
        
        paid_date = request.data.get('paid_date', timezone.now().date())
        
        invoice.knowledge_tax_paid = True
        invoice.knowledge_tax_paid_date = paid_date
        invoice.save()
        
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

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
    Optimized with select_related and prefetch_related for fast loading.
    """
    queryset = Payment.objects.select_related(
        'invoice',
        'invoice__tenant'
    ).prefetch_related(
        'cheques'
    ).all().order_by('-payment_date', '-id')
    serializer_class = PaymentSerializer
    permission_classes = [CanPerformFinancialCommand]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['invoice', 'invoice__tenant', 'payment_date', 'payment_method', 'reference_number']

    def get_queryset(self):
        return scope_payments(super().get_queryset(), self.request.user)

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
        # Don't use .copy() on request.data to avoid deepcopy of file objects
        # Instead, build a new dict manually
        data = {}
        for key in request.data.keys():
            data[key] = request.data.get(key)
        
        # Helper: Restructure flat FormData fields into nested cheque_details for Serializer
        if data.get('payment_method') == 'CHECK':
            if 'cheque_number' not in data:
                return Response({"error": "Cheque Number is required for Check payments."}, status=status.HTTP_400_BAD_REQUEST)
            
            cheque_data = {
                'cheque_number': data.get('cheque_number'),
                'bank_name': data.get('bank_name'),
                'drawer_name': data.get('drawer_name'),
                'cheque_date': data.get('cheque_date'),
                'amount': data.get('amount'),
                'note': data.get('note') or data.get('reference_number'),
            }
            # Handle File upload for cheque
            if 'cheque_image' in request.FILES:
                cheque_data['cheque_image'] = request.FILES['cheque_image']
            elif 'cheque_image' in data and hasattr(data['cheque_image'], 'read'):
                 cheque_data['cheque_image'] = data['cheque_image']
            
            data['cheque_details'] = cheque_data

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        # Extract validated data
        payment_data = {**serializer.validated_data}
        
        # FALLBACK: If serializer dropped cheque_details (e.g. strict model matching), force inject it
        if 'cheque_details' not in payment_data and 'cheque_details' in data:
            payment_data['cheque_details'] = data['cheque_details']

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
        lang = request.query_params.get('lang', 'en')
        buffer = generate_receipt_pdf(payment, lang=lang)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Receipt_{payment.id}.pdf"'
        return response
