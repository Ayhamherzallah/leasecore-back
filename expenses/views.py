from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import Expense, ExpenseCategory
from .serializers import ExpenseSerializer, ExpenseCategorySerializer
from .services import ExpenseService
from billing.pdf import generate_expense_pdf

class ExpenseViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    """
    STRICT IMMUTABLE EXPENSES.
    Allow: GET (List/Retrieve), POST (Create)
    Deny: PUT, PATCH, DELETE
    """
    queryset = Expense.objects.all().order_by('-expense_date', '-id')
    serializer_class = ExpenseSerializer
    permission_classes = [] # TODO: Add role-based permissions
    
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['unit', 'building', 'category']

    def create(self, request, *args, **kwargs):
        """
        POST /api/expenses/
        Strict delegation to ExpenseService.record_expense
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
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
        buffer = generate_expense_pdf(expense)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Voucher_{expense.id}.pdf"'
        return response

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by('name')
    serializer_class = ExpenseCategorySerializer
    permission_classes = []
