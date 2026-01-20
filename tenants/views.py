from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from .models import Tenant, Contract, TenantDocument
from properties.models import Unit
from .serializers import TenantSerializer, ContractSerializer

import logging
logger = logging.getLogger(__name__)

class TenantViewSet(viewsets.ModelViewSet):
    """
    Standard ViewSet for managing Tenants.
    Supports tax_number and multiple document uploads.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Handle Documents
        documents = request.FILES.getlist('documents')
        if documents:
            tenant = serializer.instance
            for file in documents:
                TenantDocument.objects.create(tenant=tenant, document=file, description=file.name)
             
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        # Handle New Documents (Append)
        documents = request.FILES.getlist('documents')
        if documents:
            for file in documents:
                TenantDocument.objects.create(tenant=instance, document=file, description=file.name)

        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        from django.db.models import ProtectedError
        instance = self.get_object()
        force = request.query_params.get('force', 'false') == 'true'
        
        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError as e:
            if not force:
                 return Response({
                    "error": "Cannot delete tenant because they have active contracts or invoices.",
                    "protected": True,
                    "detail": str(e)
                 }, status=status.HTTP_400_BAD_REQUEST)
            
            # Force Delete Logic
            try:
                with transaction.atomic():
                     # 1. Delete Payments associated with Invoices of this Tenant
                     # Invoices are protected by Payments.
                     # We iterate to be safe, or utilize related name
                     
                     # Get Invoices
                     invoices = instance.invoices.all()
                     for inv in invoices:
                         # Delete payments (Cheques cascade)
                         inv.payments.all().delete()
                         inv.delete()
                     
                     # 2. Delete Contracts
                     # Contracts protect Tenant.
                     instance.contracts.all().delete()
                     
                     # 3. Delete Tenant
                     instance.delete()
                     
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as inner_e:
                logger.error(f"Force delete failed: {inner_e}")
                return Response({"error": f"Force delete failed: {str(inner_e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ContractViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Contracts.
    Includes custom actions for termination.
    """
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    filterset_fields = ['tenant', 'unit', 'status']

    def create(self, request, *args, **kwargs):
        logger.info(f"Creating Contract Payload: {request.data}")
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        contract = self.get_object()
        
        if contract.status not in ['ACTIVE', 'DRAFT']:
            return Response(
                {"error": "Only Active or Draft contracts can be terminated."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Atomic transaction to ensure data integrity
        with transaction.atomic():
            # 1. Update Contract
            contract.status = 'TERMINATED'
            contract.end_date = request.data.get('end_date', timezone.now().date())
            contract.save()
            
            # 2. Update Unit Status
            unit = contract.unit
            unit.status = 'VACANT'
            unit.save()

        return Response(ContractSerializer(contract).data)

    @action(detail=True, methods=['post'])
    def generate_schedule(self, request, pk=None):
        """
        Generates invoices. 
        If 'installments' is provided in body, uses that.
        Otherwise, auto-generates based on frequency.
        """
        contract = self.get_object()
        from billing.services import BillingService
        from datetime import date, timedelta
        import calendar

        # 1. Check for manual installments
        manual_installments = request.data.get('installments')
        if manual_installments:
            BillingService.create_schedule(contract, manual_installments)
            return Response({"message": f"Successfully scheduled {len(manual_installments)} payments."})

        def add_months(sourcedate, months):
            month = sourcedate.month - 1 + months
            year = sourcedate.year + month // 12
            month = month % 12 + 1
            day = min(sourcedate.day, calendar.monthrange(year, month)[1])
            return date(year, month, day)

        freq_map = {
            'MONTHLY': 1,
            'QUARTERLY': 3,
            'BIANNUALLY': 6,
            'YEARLY': 12
        }
        
        interval = freq_map.get(contract.payment_frequency, 1)
        
        current_date = contract.start_date
        installments = []
        
        # Look ahead up to end_date
        while current_date < contract.end_date:
            # Check if invoice exists (rough check: same month/year)
            exists = contract.invoices.filter(
                issue_date__year=current_date.year,
                issue_date__month=current_date.month
            ).exists()
            
            if not exists:
                installments.append({
                    'due_date': current_date.isoformat(),
                    'amount': contract.rent_amount
                })
            
            current_date = add_months(current_date, interval)
            
        if installments:
            BillingService.create_schedule(contract, installments)
            return Response({"message": f"Generated {len(installments)} invoices.", "count": len(installments)})
        else:
            return Response({"message": "No new invoices needed.", "count": 0})

    def perform_create(self, serializer):
        from billing.services import BillingService
        from django.core.exceptions import ValidationError as DjangoValidationError
        from rest_framework.exceptions import ValidationError as DRFValidationError
        
        logger.info(f"Performing Create: Validated Data: {serializer.validated_data}")
        
        try:
            with transaction.atomic():
                contract = serializer.save()
                
                # Check for installments in the request
                installments = self.request.data.get('installments', [])
                logger.info(f"Installments provided: {len(installments)} items")
                
                if installments:
                     BillingService.create_schedule(contract, installments)
                else:
                     # Fallback if no specific schedule: create just one for start date
                     BillingService.create_schedule(contract, [{'due_date': contract.start_date, 'amount': contract.rent_amount}])
        except DjangoValidationError as e:
            # Re-raise as DRF ValidationError to return 400 Bad Request instead of 500
            raise DRFValidationError({"detail": e.messages if hasattr(e, 'messages') else str(e)})
