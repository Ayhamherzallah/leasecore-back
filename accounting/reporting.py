from django.db.models import Sum, Q
from .models import LedgerEntry
from datetime import date, datetime

class ReportingService:
    @staticmethod
    def _scope_ids(user, building_id=None):
        """
        Returns the list of building ids a user's reports may include, or None
        for unrestricted (platform admin with no specific building requested).
        If a building_id is requested, it's honoured only when accessible.
        """
        from users.utils import is_platform_admin
        from users.building_access import get_accessible_building_ids

        admin = is_platform_admin(user) if user else False
        allowed = None if admin else (get_accessible_building_ids(user) if user else [])

        if building_id:
            try:
                bid = int(building_id)
            except (TypeError, ValueError):
                return allowed if not admin else None
            if allowed is None or bid in allowed:
                return [bid]
            return [-1]  # requested a building the user can't access -> empty

        if admin:
            return None
        return allowed if allowed else [-1]

    @staticmethod
    def get_profit_loss(start, end, user=None, building_id=None):
        """
        Generates P&L numbers from the GL with full details.
        """
        ids = ReportingService._scope_ids(user, building_id)
        # Fetch detailed entries
        entries = LedgerEntry.objects.filter(
            transaction_date__range=[start, end],
            account_type__in=[LedgerEntry.AccountType.REVENUE, LedgerEntry.AccountType.EXPENSE]
        ).order_by('account_name', 'transaction_date')
        if ids is not None:
            entries = entries.filter(building_id__in=ids)

        # Group by Account
        revenue_map = {}
        expense_map = {}
        
        total_revenue = 0
        total_expenses = 0
        
        for entry in entries:
            amount = 0
            # For Revenue: Net = Credit - Debit
            if entry.account_type == LedgerEntry.AccountType.REVENUE:
                amount = (entry.credit or 0) - (entry.debit or 0)
                if amount == 0: continue
                
                if entry.account_name not in revenue_map:
                    revenue_map[entry.account_name] = {'account': entry.account_name, 'amount': 0, 'details': []}
                
                revenue_map[entry.account_name]['amount'] += amount
                revenue_map[entry.account_name]['details'].append({
                    'date': entry.transaction_date,
                    'description': entry.description,
                    'amount': amount
                })
                total_revenue += amount

            # For Expense: Net = Debit - Credit
            elif entry.account_type == LedgerEntry.AccountType.EXPENSE:
                amount = (entry.debit or 0) - (entry.credit or 0)
                if amount == 0: continue
                
                if entry.account_name not in expense_map:
                    expense_map[entry.account_name] = {'account': entry.account_name, 'amount': 0, 'details': []}
                
                expense_map[entry.account_name]['amount'] += amount
                expense_map[entry.account_name]['details'].append({
                    'date': entry.transaction_date,
                    'description': entry.description,
                    'amount': amount
                })
                total_expenses += amount
        
        return {
            'start_date': start,
            'end_date': end,
            'revenue_breakdown': list(revenue_map.values()),
            'total_revenue': total_revenue,
            'expense_breakdown': list(expense_map.values()),
            'total_expenses': total_expenses,
            'net_profit': total_revenue - total_expenses
        }

    @staticmethod
    def get_revenue_report(start, end, user=None, building_id=None):
        from billing.models import Invoice, Payment

        ids = ReportingService._scope_ids(user, building_id)
        # Base P&L data
        pl_data = ReportingService.get_profit_loss(start, end, user=user, building_id=building_id)
        
        # Extended Breakdown (Cash Basis)
        payments = Payment.objects.filter(
            payment_date__range=[start, end]
        ).exclude(invoice__status='VOID')
        if ids is not None:
            payments = payments.filter(invoice__building_id__in=ids)
        
        by_tenant = payments.values('invoice__tenant__name').annotate(total=Sum('amount')).order_by('-total')
        by_unit = payments.values('invoice__contract__unit__unit_number').annotate(total=Sum('amount')).order_by('-total')
        
        # Rename keys to match frontend expectations if needed, but annotate names are used directly
        # Frontend likely expects 'tenant__name' and 'contract__unit__unit_number' keys from previous .values()
        # Modifying the keys in result list to match previous output format if necessary.
        # Previous: values('tenant__name') -> key is 'tenant__name'
        # New: values('invoice__tenant__name') -> key is 'invoice__tenant__name'
        
        # To maintain compatibility with frontend which likely uses 'tenant__name', I will map them.
        
        tenant_data = []
        for item in by_tenant:
            tenant_data.append({
                'tenant__name': item['invoice__tenant__name'],
                'total': item['total']
            })
            
        unit_data = []
        for item in by_unit:
            unit_data.append({
                'contract__unit__unit_number': item['invoice__contract__unit__unit_number'],
                'total': item['total']
            })
        
        return {
            'total_revenue': pl_data['total_revenue'],
            'by_account': pl_data['revenue_breakdown'],
            'by_tenant': tenant_data,
            'by_unit': unit_data
        }

    @staticmethod
    def get_expense_report(start, end, user=None, building_id=None):
        from expenses.models import Expense

        ids = ReportingService._scope_ids(user, building_id)
        pl_data = ReportingService.get_profit_loss(start, end, user=user, building_id=building_id)
        
        expenses = Expense.objects.filter(expense_date__range=[start, end])
        if ids is not None:
            expenses = expenses.filter(building_id__in=ids)
        by_category = expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')
        by_unit = expenses.exclude(unit=None).values('unit__unit_number').annotate(total=Sum('amount')).order_by('-total')
        
        return {
            'total_expenses': pl_data['total_expenses'],
            'by_account': pl_data['expense_breakdown'],
            'by_category': list(by_category),
            'by_unit': list(by_unit)
        }

    @staticmethod
    def get_cash_flow(start, end, user=None, building_id=None):
        from billing.models import Payment
        from expenses.models import Expense

        ids = ReportingService._scope_ids(user, building_id)
        payments = Payment.objects.filter(payment_date__range=[start, end])
        expenses = Expense.objects.filter(expense_date__range=[start, end])
        if ids is not None:
            payments = payments.filter(invoice__building_id__in=ids)
            expenses = expenses.filter(building_id__in=ids)
        total_in = payments.aggregate(s=Sum('amount'))['s'] or 0
        total_out = expenses.aggregate(s=Sum('amount'))['s'] or 0
        
        return {
            'total_in': total_in,
            'total_out': total_out,
            'net': total_in - total_out
        }

    @staticmethod
    def get_tenant_summary(user=None, building_id=None):
        from tenants.models import Tenant
        from billing.models import Payment
        from django.db.models import Value, DecimalField, OuterRef, Subquery
        from django.db.models.functions import Coalesce
        from users.building_access import scope_tenants, is_platform_admin

        # Resolve the visible tenant ids on a clean queryset first, so the
        # aggregation below joins ONLY the invoices relation (no join fan-out).
        scoped = Tenant.objects.all()
        if user and not is_platform_admin(user):
            scoped = scope_tenants(scoped, user)
        tenant_ids = set(scoped.values_list('pk', flat=True))

        building_q = Q()
        if building_id:
            in_building = set(
                Tenant.objects.filter(
                    Q(contracts__unit__floor__building_id=building_id)
                    | Q(invoices__building_id=building_id)
                    | Q(invoices__contract__unit__floor__building_id=building_id)
                ).values_list('pk', flat=True)
            )
            tenant_ids &= in_building
            building_q = (
                Q(invoice__building_id=building_id)
                | Q(invoice__contract__unit__floor__building_id=building_id)
            )

        dec = DecimalField(max_digits=14, decimal_places=2)
        inv_q = ~Q(invoices__status='VOID')
        if building_id:
            inv_q &= (
                Q(invoices__building_id=building_id)
                | Q(invoices__contract__unit__floor__building_id=building_id)
            )

        last_pay_sq = (
            Payment.objects
            .filter(Q(invoice__tenant=OuterRef('pk')) & building_q)
            .exclude(invoice__status='VOID')
            .order_by('-payment_date')
            .values('payment_date')[:1]
        )

        qs = Tenant.objects.filter(pk__in=tenant_ids).annotate(
            _total=Coalesce(Sum('invoices__total_amount', filter=inv_q), Value(0), output_field=dec),
            _paid=Coalesce(Sum('invoices__paid_amount', filter=inv_q), Value(0), output_field=dec),
            _last=Subquery(last_pay_sq),
        )

        data = [{
            'id': t.id,
            'name': t.name,
            'total_invoiced': t._total,
            'total_paid': t._paid,
            'balance': (t._total or 0) - (t._paid or 0),
            'last_payment_date': t._last,
        } for t in qs]
        return sorted(data, key=lambda x: x['balance'], reverse=True)

    @staticmethod
    def get_unit_performance(start, end, user=None, building_id=None):
        from properties.models import Unit
        from billing.models import Payment, Invoice
        from expenses.models import Expense
        from django.db.models import Value, DecimalField, OuterRef, Subquery
        from django.db.models.functions import Coalesce

        ids = ReportingService._scope_ids(user, building_id)
        units = Unit.objects.all()
        if ids is not None:
            units = units.filter(floor__building_id__in=ids)

        dec = DecimalField(max_digits=14, decimal_places=2)

        def _sum(qs, field):
            """Correlated per-unit Sum subquery (no join fan-out)."""
            return Coalesce(Subquery(qs.values('s')[:1], output_field=dec), Value(0), output_field=dec)

        rev_qs = (Payment.objects
                  .filter(invoice__contract__unit=OuterRef('pk'), payment_date__range=[start, end])
                  .exclude(invoice__status='VOID')
                  .values('invoice__contract__unit').annotate(s=Sum('amount')))
        cost_qs = (Expense.objects
                   .filter(unit=OuterRef('pk'), expense_date__range=[start, end])
                   .values('unit').annotate(s=Sum('amount')))
        inv_total_qs = (Invoice.objects.filter(contract__unit=OuterRef('pk')).exclude(status='VOID')
                        .values('contract__unit').annotate(s=Sum('total_amount')))
        inv_paid_qs = (Invoice.objects.filter(contract__unit=OuterRef('pk')).exclude(status='VOID')
                       .values('contract__unit').annotate(s=Sum('paid_amount')))

        units = units.annotate(
            _rev=_sum(rev_qs, 'amount'),
            _cost=_sum(cost_qs, 'amount'),
            _inv_total=_sum(inv_total_qs, 'total_amount'),
            _inv_paid=_sum(inv_paid_qs, 'paid_amount'),
        )

        data = []
        for u in units:
            rev = u._rev or 0
            cost = u._cost or 0
            balance = (u._inv_total or 0) - (u._inv_paid or 0)
            data.append({
                'unit': u.unit_number,
                'status': u.status,
                'revenue': rev,
                'expenses': cost,
                'net': rev - cost,
                'balance': balance
            })
        return sorted(data, key=lambda x: x['net'], reverse=True)
