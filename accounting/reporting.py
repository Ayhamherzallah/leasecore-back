from django.db.models import Sum, Q
from .models import LedgerEntry
from datetime import date, datetime

class ReportingService:
    @staticmethod
    def get_profit_loss(start, end):
        """
        Generates P&L numbers from the GL with full details.
        """
        # Fetch detailed entries
        entries = LedgerEntry.objects.filter(
            transaction_date__range=[start, end],
            account_type__in=[LedgerEntry.AccountType.REVENUE, LedgerEntry.AccountType.EXPENSE]
        ).order_by('account_name', 'transaction_date')

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
    def get_revenue_report(start, end):
        from billing.models import Invoice, Payment
        
        # Base P&L data
        pl_data = ReportingService.get_profit_loss(start, end)
        
        # Extended Breakdown (Cash Basis)
        payments = Payment.objects.filter(
            payment_date__range=[start, end]
        ).exclude(invoice__status='VOID')
        
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
    def get_expense_report(start, end):
        from expenses.models import Expense
        
        pl_data = ReportingService.get_profit_loss(start, end)
        
        expenses = Expense.objects.filter(expense_date__range=[start, end])
        by_category = expenses.values('category__name').annotate(total=Sum('amount')).order_by('-total')
        by_unit = expenses.exclude(unit=None).values('unit__unit_number').annotate(total=Sum('amount')).order_by('-total')
        
        return {
            'total_expenses': pl_data['total_expenses'],
            'by_account': pl_data['expense_breakdown'],
            'by_category': list(by_category),
            'by_unit': list(by_unit)
        }

    @staticmethod
    def get_cash_flow(start, end):
        from billing.models import Payment
        from expenses.models import Expense
        
        payments = Payment.objects.filter(payment_date__range=[start, end])
        total_in = payments.aggregate(s=Sum('amount'))['s'] or 0
        
        expenses = Expense.objects.filter(expense_date__range=[start, end])
        total_out = expenses.aggregate(s=Sum('amount'))['s'] or 0
        
        return {
            'total_in': total_in,
            'total_out': total_out,
            'net': total_in - total_out
        }

    @staticmethod
    def get_tenant_summary():
        from tenants.models import Tenant
        from billing.models import Invoice, Payment
        
        tenants = Tenant.objects.all()
        data = []
        for t in tenants:
            invs = Invoice.objects.filter(tenant=t).exclude(status='VOID')
            total = invs.aggregate(s=Sum('total_amount'))['s'] or 0
            paid = invs.aggregate(s=Sum('paid_amount'))['s'] or 0
            last_pay = Payment.objects.filter(invoice__tenant=t).order_by('-payment_date').first()
            
            data.append({
                'id': t.id,
                'name': t.name,
                'total_invoiced': total,
                'total_paid': paid,
                'balance': total - paid,
                'last_payment_date': last_pay.payment_date if last_pay else None
            })
        return sorted(data, key=lambda x: x['balance'], reverse=True)

    @staticmethod
    def get_unit_performance(start, end):
        from properties.models import Unit
        from billing.models import Payment, Invoice
        from expenses.models import Expense
        
        units = Unit.objects.all()
        data = []
        for u in units:
            # Cash Basis Revenue: Payments received for invoices linked to this unit
            rev = Payment.objects.filter(
                invoice__contract__unit=u, 
                payment_date__range=[start, end]
            ).exclude(invoice__status='VOID').aggregate(s=Sum('amount'))['s'] or 0
            
            cost = Expense.objects.filter(unit=u, expense_date__range=[start, end]).aggregate(s=Sum('amount'))['s'] or 0
            
            # Total Outstanding Balance (Current debt)
            unit_invoices = Invoice.objects.filter(contract__unit=u).exclude(status='VOID')
            total_inv = unit_invoices.aggregate(s=Sum('total_amount'))['s'] or 0
            total_paid = unit_invoices.aggregate(s=Sum('paid_amount'))['s'] or 0
            balance = total_inv - total_paid
            
            data.append({
                'unit': u.unit_number,
                'status': u.status,
                'revenue': rev,
                'expenses': cost,
                'net': rev - cost,
                'balance': balance
            })
        return sorted(data, key=lambda x: x['net'], reverse=True)
