from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from .models import LedgerEntry
from .serializers import LedgerEntrySerializer
from billing.pdf import generate_ledger_report
from users.building_access import scope_ledger, get_accessible_building_ids
from users.utils import is_platform_admin

class LedgerEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-Only View for the General Ledger.
    Allows filtering by date ranges and account.
    """
    queryset = LedgerEntry.objects.all().order_by('-transaction_date', '-id')
    serializer_class = LedgerEntrySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    
    # Explicitly configure filter fields to support ranges
    filterset_fields = {
        'transaction_date': ['gte', 'lte'],
        'account_name': ['icontains', 'exact'],
        'account_type': ['exact'],
        'building': ['exact'],
    }
    
    search_fields = ['description', 'account_name']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return scope_ledger(super().get_queryset(), self.request.user)

    @action(detail=False, methods=['get'])
    def report(self, request):
        """
        GET /api/accounting/ledger/report/
        Returns PDF report of filtered ledger entries.
        """
        # 1. Apply Filters
        queryset = self.filter_queryset(self.get_queryset())
        
        building_id = request.query_params.get('building')
        start = request.query_params.get('transaction_date__gte')
        end = request.query_params.get('transaction_date__lte')
        date_text = None
        if start and end:
            date_text = f"{start} - {end}"
        elif start:
            date_text = f"من {start}"
        elif end:
            date_text = f"حتى {end}"
            
        # 3. Generate PDF
        lang = request.query_params.get('lang', 'en')
        buffer = generate_ledger_report(queryset, date_text, building_id=building_id, lang=lang)
        
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="General_Ledger.pdf"'
        return response

from .reporting import ReportingService
from datetime import date
from .pdf_reporting import (
    generate_profit_loss_pdf, generate_revenue_pdf, 
    generate_expense_report_pdf, generate_cash_flow_pdf,
    generate_tenant_report_pdf, generate_unit_report_pdf
)

class ReportsViewSet(viewsets.ViewSet):
    """
    Dedicated ViewSet for Financial Reports (Aggregates).
    """
    permission_classes = [IsAuthenticated]

    def _scoped_ledger_filter(self, request):
        if is_platform_admin(request.user):
            return {}
        ids = get_accessible_building_ids(request.user)
        return {'building_id__in': ids} if ids else {'building_id__in': [-1]}

    def _get_dates(self, request):
        today = date.today()
        start_default = today.replace(day=1).isoformat()
        end_default = today.isoformat()
        start = request.query_params.get('start_date', start_default)
        end = request.query_params.get('end_date', end_default)
        return start, end

    @action(detail=False, methods=['get'], url_path='profit-loss')
    def profit_loss(self, request):
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        data = ReportingService.get_profit_loss(start, end, user=request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='revenue')
    def revenue(self, request):
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        data = ReportingService.get_revenue_report(start, end, user=request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='expenses')
    def expenses(self, request):
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        data = ReportingService.get_expense_report(start, end, user=request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='cash-flow')
    def cash_flow(self, request):
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        data = ReportingService.get_cash_flow(start, end, user=request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='tenants')
    def tenants(self, request):
        building_id = request.query_params.get('building')
        data = ReportingService.get_tenant_summary(request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='units')
    def units(self, request):
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        data = ReportingService.get_unit_performance(start, end, user=request.user, building_id=building_id)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        report_type = request.query_params.get('type')
        start, end = self._get_dates(request)
        building_id = request.query_params.get('building')
        date_text = f"{start} إلى {end}" if start and end else None
        
        buffer = None
        filename = f"Report_{report_type}.pdf"
        
        if report_type == 'PROFIT_LOSS':
            data = ReportingService.get_profit_loss(start, end, user=request.user, building_id=building_id)
            buffer = generate_profit_loss_pdf(data, date_text, building_id=building_id)
            
        elif report_type == 'REVENUE':
            data = ReportingService.get_revenue_report(start, end, user=request.user, building_id=building_id)
            buffer = generate_revenue_pdf(data, date_text, building_id=building_id)
            
        elif report_type == 'EXPENSES':
            data = ReportingService.get_expense_report(start, end, user=request.user, building_id=building_id)
            buffer = generate_expense_report_pdf(data, date_text, building_id=building_id)
            
        elif report_type == 'CASH_FLOW':
            data = ReportingService.get_cash_flow(start, end, user=request.user, building_id=building_id)
            buffer = generate_cash_flow_pdf(data, date_text, building_id=building_id)
            
        elif report_type == 'TENANTS':
            data = ReportingService.get_tenant_summary(request.user, building_id=building_id)
            buffer = generate_tenant_report_pdf(data, building_id=building_id)
            
        elif report_type == 'UNITS':
            data = ReportingService.get_unit_performance(start, end, user=request.user, building_id=building_id)
            buffer = generate_unit_report_pdf(data, date_text, building_id=building_id)
        
        else:
             return Response({"error": "Invalid Type"}, status=400)
             
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response