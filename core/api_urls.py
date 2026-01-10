from django.urls import path, include
from rest_framework.routers import DefaultRouter
from billing.views import InvoiceViewSet, PaymentViewSet, ChequeViewSet
from expenses.views import ExpenseViewSet, ExpenseCategoryViewSet
from accounting.views import LedgerEntryViewSet, ReportsViewSet
from tenants.views import TenantViewSet, ContractViewSet
from users.views import UserViewSet
from properties.views import BuildingViewSet, FloorViewSet, UnitViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'billing/invoices', InvoiceViewSet)
router.register(r'billing/payments', PaymentViewSet)
router.register(r'billing/cheques', ChequeViewSet)
router.register(r'expense-categories', ExpenseCategoryViewSet)
router.register(r'expenses', ExpenseViewSet)
router.register(r'accounting/ledger', LedgerEntryViewSet)
router.register(r'reports', ReportsViewSet, basename='reports')
router.register(r'tenants', TenantViewSet)
router.register(r'contracts', ContractViewSet)
router.register(r'properties/buildings', BuildingViewSet)
router.register(r'properties/floors', FloorViewSet)
router.register(r'properties/units', UnitViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
