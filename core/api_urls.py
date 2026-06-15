from django.urls import path, include
from rest_framework.routers import DefaultRouter
from billing.views import InvoiceViewSet, PaymentViewSet, ChequeViewSet, InvoiceTypeViewSet
from billing.knowledge_tax_report import knowledge_tax_report
from expenses.views import (
    ExpenseViewSet, ExpenseCategoryViewSet, FixedCostViewSet, FixedCostOccurrenceViewSet,
)
from accounting.views import LedgerEntryViewSet, ReportsViewSet
from tenants.views import TenantViewSet, ContractViewSet
from users.views import UserViewSet
from properties.views import BuildingViewSet, FloorViewSet, UnitViewSet
from pdf_templates.views import PdfBrandingViewSet
from imports.views import ImportViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'billing/invoices', InvoiceViewSet)
router.register(r'billing/payments', PaymentViewSet)
router.register(r'billing/cheques', ChequeViewSet)
router.register(r'billing/invoice-types', InvoiceTypeViewSet)
router.register(r'expense-categories', ExpenseCategoryViewSet)
router.register(r'fixed-costs', FixedCostViewSet)
router.register(r'fixed-cost-occurrences', FixedCostOccurrenceViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'accounting/ledger', LedgerEntryViewSet)
router.register(r'reports', ReportsViewSet, basename='reports')
router.register(r'tenants', TenantViewSet, basename='tenant')
router.register(r'contracts', ContractViewSet, basename='contract')
router.register(r'properties/buildings', BuildingViewSet)
router.register(r'properties/floors', FloorViewSet)
router.register(r'properties/units', UnitViewSet)
router.register(r'pdf-branding', PdfBrandingViewSet, basename='pdf-branding')
router.register(r'imports', ImportViewSet, basename='imports')

from core.views import demo_request

urlpatterns = [
    path('', include(router.urls)),
    path('billing/knowledge-tax-report/', knowledge_tax_report, name='knowledge-tax-report'),
    path('demo-request/', demo_request, name='demo-request'),
]
