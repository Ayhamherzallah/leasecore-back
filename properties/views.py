from rest_framework import viewsets, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from .models import Building, Floor, Unit
from .serializers import BuildingSerializer, FloorSerializer, UnitSerializer

class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = []

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this building because it contains floors or units linked to other records."},
                status=status.HTTP_400_BAD_REQUEST
            )

class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.all().order_by('number')
    serializer_class = FloorSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['building']

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {"error": "Cannot delete this floor because it contains units linked to other records."},
                status=status.HTTP_400_BAD_REQUEST
            )

class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all().order_by('unit_number')
    serializer_class = UnitSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['floor', 'floor__building', 'status']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        force = request.query_params.get('force', 'false') == 'true'

        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            if force:
                # Cascade Delete Logic - Adjusted to PRESERVE Financials
                
                # 1. Detach Expenses (Preserve record, just unlink unit)
                if hasattr(instance, 'expenses'):
                    instance.expenses.update(unit=None)
                
                # 2. Handle Contracts (Must delete Contract because unit is non-nullable, BUT preserve Invoices)
                if hasattr(instance, 'contracts'):
                    for contract in instance.contracts.all():
                        # Detach Invoices from Contract (set contract=None)
                        if hasattr(contract, 'invoices'):
                            # Use update() for bulk efficiency
                            contract.invoices.update(contract=None)
                        
                        # Now we can safely delete the contract without losing invoices
                        contract.delete()
                
                # 3. Delete Unit
                instance.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {"error": "Cannot delete this unit because it is linked to history (Contracts/Invoices). Use force delete to remove all history.", "can_force": True},
                    status=status.HTTP_400_BAD_REQUEST
                )
