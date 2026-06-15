from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import ProtectedError
from .models import Building, Floor, Unit
from .serializers import BuildingSerializer, FloorSerializer, UnitSerializer
from users.utils import get_accessible_buildings
from users.building_access import scope_floors, scope_units, user_can_access_building
from users.permissions import CanManageBuildingOperations

class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = [IsAuthenticated, CanManageBuildingOperations]

    def get_queryset(self):
        return get_accessible_buildings(self.request.user).order_by('name')

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
    permission_classes = [IsAuthenticated, CanManageBuildingOperations]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['building']

    def get_queryset(self):
        return scope_floors(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        building = serializer.validated_data.get('building')
        if building and not user_can_access_building(self.request.user, building.id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have access to this building.')
        serializer.save()

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
    permission_classes = [IsAuthenticated, CanManageBuildingOperations]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['floor', 'floor__building', 'status']

    def get_queryset(self):
        return scope_units(super().get_queryset(), self.request.user)

    def perform_create(self, serializer):
        floor = serializer.validated_data.get('floor')
        if floor and not user_can_access_building(self.request.user, floor.building_id):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have access to this building.')
        serializer.save()

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
