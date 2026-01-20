from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q, Count
from decimal import Decimal
from .models import Invoice
from expenses.models import Expense, ExpenseCategory

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def knowledge_tax_report(request):
    """
    Generate a comprehensive Knowledge Tax (ضريبة المعارف) report.
    
    Returns:
    - Total collected from tenants
    - Total paid to municipality (via expenses)
    - Outstanding amount
    - Breakdown by unit
    - Payment status
    """
    
    # Get date range from query params (optional)
    from_date = request.query_params.get('from_date')
    to_date = request.query_params.get('to_date')
    
    # Base queryset for invoices with knowledge tax
    invoice_qs = Invoice.objects.filter(knowledge_tax_amount__gt=0)
    
    if from_date:
        invoice_qs = invoice_qs.filter(issue_date__gte=from_date)
    if to_date:
        invoice_qs = invoice_qs.filter(issue_date__lte=to_date)
    
    # Calculate totals from invoices
    # Collected from tenants = Knowledge Tax on Paid/Partially Paid invoices
    invoice_stats = invoice_qs.aggregate(
        total_billed=Sum('knowledge_tax_amount'),
        total_collected=Sum('knowledge_tax_amount', filter=Q(status__in=['PAID', 'PARTIALLY_PAID'])),
        count_paid=Count('id', filter=Q(status__in=['PAID', 'PARTIALLY_PAID'])),
        count_unpaid=Count('id', filter=Q(status='ISSUED'))
    )
    
    # Get expenses for knowledge tax payments
    # Search for categories containing "Knowledge" or "معارف"
    expense_qs = Expense.objects.filter(
        Q(category__name__icontains='Knowledge') | 
        Q(category__name__icontains='معارف')
    )
    
    if from_date:
        expense_qs = expense_qs.filter(expense_date__gte=from_date)
    if to_date:
        expense_qs = expense_qs.filter(expense_date__lte=to_date)
    
    expense_stats = expense_qs.aggregate(
        total_paid_to_municipality=Sum('amount')
    )
    
    # Breakdown by unit
    unit_breakdown = invoice_qs.values(
        'contract__unit__id',
        'contract__unit__unit_number',
        'contract__unit__floor__name'
    ).annotate(
        total_tax=Sum('knowledge_tax_amount'),
        paid_tax=Sum('knowledge_tax_amount', filter=Q(status__in=['PAID', 'PARTIALLY_PAID'])),
        unpaid_tax=Sum('knowledge_tax_amount', filter=Q(status='ISSUED'))
    ).order_by('-total_tax')
    
    # Recent invoices with knowledge tax
    recent_invoices = invoice_qs.select_related(
        'tenant', 'contract__unit'
    ).order_by('-issue_date')[:20].values(
        'id',
        'invoice_number',
        'tenant__name',
        'contract__unit__unit_number',
        'issue_date',
        'knowledge_tax_amount',
        'knowledge_tax_paid',
        'knowledge_tax_paid_date'
    )
    
    # Recent expenses
    recent_expenses = expense_qs.select_related('unit').order_by('-expense_date')[:20].values(
        'id',
        'expense_date',
        'amount',
        'description',
        'unit__unit_number',
        'invoice_reference'
    )
    
    return Response({
        'summary': {
            'total_billed': invoice_stats['total_billed'] or Decimal('0.00'),
            'total_collected_from_tenants': invoice_stats['total_collected'] or Decimal('0.00'),
            'total_paid_to_municipality': expense_stats['total_paid_to_municipality'] or Decimal('0.00'),
            'outstanding_to_collect': (invoice_stats['total_billed'] or Decimal('0.00')) - (invoice_stats['total_collected'] or Decimal('0.00')),
            'count_paid': invoice_stats['count_paid'] or 0,
            'count_unpaid': invoice_stats['count_unpaid'] or 0
        },
        'unit_breakdown': list(unit_breakdown),
        'recent_invoices': list(recent_invoices),
        'recent_expenses': list(recent_expenses)
    })
