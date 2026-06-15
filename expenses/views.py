from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import Expense, ExpenseCategory, FixedCost, FixedCostOccurrence
from .serializers import (
    ExpenseSerializer, ExpenseCategorySerializer,
    FixedCostSerializer, FixedCostOccurrenceSerializer,
)
from .services import ExpenseService, FixedCostService
from billing.pdf import generate_expense_pdf
from users.building_access import (
    scope_expenses, user_can_access_building, scope_catalog,
    scope_fixed_costs, scope_fixed_cost_occurrences,
)
from users.utils import is_platform_admin
from users.permissions import CanRecordExpenses, CanPerformFinancialCommand

class ExpenseViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    STRICT IMMUTABLE EXPENSES.
    Allow: GET (List/Retrieve), POST (Create)
    Deny: PUT, PATCH, DELETE
    """
    queryset = Expense.objects.select_related('category', 'unit', 'building').order_by('-expense_date', '-id')
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated, CanRecordExpenses]
    
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['unit', 'building', 'category', 'cost_type']

    def get_queryset(self):
        return scope_expenses(super().get_queryset(), self.request.user)

    def create(self, request, *args, **kwargs):
        """
        POST /api/expenses/
        Strict delegation to ExpenseService.record_expense
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        building = serializer.validated_data.get('building')
        if building and not user_can_access_building(request.user, building.id):
            return Response({"error": "You do not have access to this building."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
             # Delegate to Service
            expense = ExpenseService.record_expense(serializer.validated_data)
            response_serializer = self.get_serializer(expense)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except ValueError as e:
             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """
        GET /api/expenses/{id}/pdf/
        Generates Expense Voucher PDF.
        """
        expense = self.get_object()
        lang = request.query_params.get('lang', 'en')
        buffer = generate_expense_pdf(expense, lang=lang)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Voucher_{expense.id}.pdf"'
        return response

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by('name')
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, CanPerformFinancialCommand]

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
            raise PermissionDenied('System default categories cannot be modified.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.building_id is None and not is_platform_admin(self.request.user):
            raise PermissionDenied('System default categories cannot be deleted.')
        instance.delete()


class FixedCostViewSet(viewsets.ModelViewSet):
    """Recurring fixed-cost templates with manual generation + confirm workflow."""
    queryset = FixedCost.objects.select_related('building', 'category', 'unit').all()
    serializer_class = FixedCostSerializer
    permission_classes = [IsAuthenticated, CanRecordExpenses]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['building', 'category', 'is_active', 'frequency']

    def get_queryset(self):
        return scope_fixed_costs(super().get_queryset(), self.request.user)

    def _check_building(self, building):
        user = self.request.user
        if not is_platform_admin(user):
            if building is None or not user_can_access_building(user, building.id):
                raise ValidationError({'building': 'A valid building you have access to is required.'})

    def perform_create(self, serializer):
        self._check_building(serializer.validated_data.get('building'))
        serializer.save()

    def perform_update(self, serializer):
        building = serializer.validated_data.get('building', serializer.instance.building)
        self._check_building(building)
        serializer.save()

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Create PENDING occurrences for all due periods up to today."""
        fixed_cost = self.get_object()
        created = FixedCostService.generate_due(fixed_cost)
        return Response({
            'created': len(created),
            'occurrences': FixedCostOccurrenceSerializer(created, many=True).data,
        })

    @action(detail=True, methods=['get'])
    def occurrences(self, request, pk=None):
        fixed_cost = self.get_object()
        qs = fixed_cost.occurrences.all().order_by('-period_date')
        return Response(FixedCostOccurrenceSerializer(qs, many=True).data)


class FixedCostOccurrenceViewSet(mixins.ListModelMixin,
                                 mixins.RetrieveModelMixin,
                                 viewsets.GenericViewSet):
    """Scheduled fixed-cost instances; confirm posts to the ledger."""
    queryset = FixedCostOccurrence.objects.select_related(
        'fixed_cost', 'fixed_cost__category', 'fixed_cost__building'
    ).all()
    serializer_class = FixedCostOccurrenceSerializer
    permission_classes = [IsAuthenticated, CanRecordExpenses]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'fixed_cost', 'fixed_cost__building']

    def get_queryset(self):
        return scope_fixed_cost_occurrences(super().get_queryset(), self.request.user)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        occurrence = self.get_object()
        paid_date = request.data.get('paid_date') or None
        try:
            FixedCostService.confirm_occurrence(occurrence, paid_date=paid_date)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        occurrence.refresh_from_db()
        return Response(self.get_serializer(occurrence).data)

    @action(detail=True, methods=['post'])
    def skip(self, request, pk=None):
        occurrence = self.get_object()
        try:
            FixedCostService.skip_occurrence(occurrence)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        occurrence.refresh_from_db()
        return Response(self.get_serializer(occurrence).data)
