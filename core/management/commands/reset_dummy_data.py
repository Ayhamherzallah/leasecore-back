from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
import datetime

from properties.models import Building, Floor, Unit
from tenants.models import Tenant, Contract
from billing.models import Invoice, Payment
from expenses.models import ExpenseCategory, Expense
from accounting.models import LedgerEntry
from accounting.services import AccountingService


class Command(BaseCommand):
    help = 'Clear all data and create dummy data for testing'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('⚠️  This will DELETE ALL DATA!'))
        confirm = input('Are you sure? Type "yes" to continue: ')
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('❌ Cancelled'))
            return

        self.stdout.write(self.style.WARNING('🗑️  Clearing all data...'))
        
        # Clear data in correct order (respecting foreign keys)
        LedgerEntry.objects.all().delete()
        Payment.objects.all().delete()
        Expense.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        Invoice.objects.all().delete()
        Contract.objects.all().delete()
        Tenant.objects.all().delete()
        Unit.objects.all().delete()
        Floor.objects.all().delete()
        Building.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS('✅ All data cleared'))
        
        self.stdout.write(self.style.WARNING('📦 Creating dummy data...'))
        
        with transaction.atomic():
            # 1. Create Building
            building = Building.objects.create(
                name="أبو رخية بلازا",
                address="شارع المدينة المنورة، عمان",
                total_area=Decimal('500.00')
            )
            self.stdout.write(f'  ✓ Created building: {building.name}')
            
            # 2. Create Floors
            floor1 = Floor.objects.create(building=building, number=1, name="الطابق الأول")
            floor2 = Floor.objects.create(building=building, number=2, name="الطابق الثاني")
            self.stdout.write(f'  ✓ Created 2 floors')
            
            # 3. Create Units
            unit101 = Unit.objects.create(
                floor=floor1,
                unit_number="101",
                area=Decimal('150.00'),
                market_rent=Decimal('1000.00'),
                status='OCCUPIED'
            )
            unit102 = Unit.objects.create(
                floor=floor1,
                unit_number="102",
                area=Decimal('200.00'),
                market_rent=Decimal('1500.00'),
                status='VACANT'
            )
            unit201 = Unit.objects.create(
                floor=floor2,
                unit_number="201",
                area=Decimal('180.00'),
                market_rent=Decimal('1200.00'),
                status='OCCUPIED'
            )
            self.stdout.write(f'  ✓ Created 3 units')
            
            # 4. Create Tenants
            tenant1 = Tenant.objects.create(
                name="محمد أحمد",
                email="mohamed@example.com",
                phone="+962791234567",
                national_id="1234567890"
            )
            tenant2 = Tenant.objects.create(
                name="سارة خالد",
                email="sara@example.com",
                phone="+962797654321",
                national_id="0987654321"
            )
            self.stdout.write(f'  ✓ Created 2 tenants')
            
            # 5. Create Contracts
            start_date = datetime.date(2026, 1, 1)
            contract1 = Contract.objects.create(
                unit=unit101,
                tenant=tenant1,
                start_date=start_date,
                end_date=start_date + datetime.timedelta(days=365),
                rent_amount=unit101.market_rent,
                payment_frequency='MONTHLY',
                status='ACTIVE'
            )
            contract2 = Contract.objects.create(
                unit=unit201,
                tenant=tenant2,
                start_date=start_date,
                end_date=start_date + datetime.timedelta(days=365),
                rent_amount=unit201.market_rent,
                payment_frequency='MONTHLY',
                status='ACTIVE'
            )
            self.stdout.write(f'  ✓ Created 2 contracts')
            
            # 6. Create Expense Categories
            categories = [
                ExpenseCategory.objects.create(name="صيانة", description="أعمال الصيانة"),
                ExpenseCategory.objects.create(name="كهرباء", description="فواتير الكهرباء"),
                ExpenseCategory.objects.create(name="نظافة", description="خدمات النظافة"),
            ]
            self.stdout.write(f'  ✓ Created {len(categories)} expense categories')
            
            # 7. Create Invoices and Payments
            invoice_count = 0
            payment_count = 0
            
            # Invoice 1 (Paid)
            inv1 = Invoice.objects.create(
                contract=contract1,
                tenant=tenant1,
                invoice_number="INV-2026-001",
                issue_date=datetime.date(2026, 1, 5),
                due_date=datetime.date(2026, 2, 5),
                total_amount=Decimal('1000.00'),
                invoice_type='RENT'
            )
            AccountingService.process_invoice_ledger(inv1)
            invoice_count += 1
            
            pay1 = Payment.objects.create(
                invoice=inv1,
                amount=Decimal('1000.00'),
                payment_date=datetime.date(2026, 1, 10),
                payment_method='BANK',
                reference_number='PAY-2026-001'
            )
            inv1.paid_amount = Decimal('1000.00')
            inv1.status = 'PAID'
            inv1.save()
            AccountingService.process_payment_ledger(pay1)
            payment_count += 1
            
            # Invoice 2 (Partially Paid)
            inv2 = Invoice.objects.create(
                contract=contract2,
                tenant=tenant2,
                invoice_number="INV-2026-002",
                issue_date=datetime.date(2026, 1, 7),
                due_date=datetime.date(2026, 2, 7),
                total_amount=Decimal('1200.00'),
                invoice_type='RENT'
            )
            AccountingService.process_invoice_ledger(inv2)
            invoice_count += 1
            
            pay2 = Payment.objects.create(
                invoice=inv2,
                amount=Decimal('600.00'),
                payment_date=datetime.date(2026, 1, 15),
                payment_method='CASH',
                reference_number='PAY-2026-002'
            )
            inv2.paid_amount = Decimal('600.00')
            inv2.status = 'PARTIALLY_PAID'
            inv2.save()
            AccountingService.process_payment_ledger(pay2)
            payment_count += 1
            
            # Invoice 3 (Unpaid)
            # Invoice 3 (Unpaid)
            inv3 = Invoice.objects.create(
                contract=contract1,
                tenant=tenant1,
                invoice_number="INV-2026-003",
                issue_date=datetime.date(2026, 2, 5),
                due_date=datetime.date(2026, 3, 5),
                total_amount=Decimal('1000.00'),
                invoice_type='RENT',
                status='ISSUED'
            )
            AccountingService.process_invoice_ledger(inv3)
            invoice_count += 1
            
            self.stdout.write(f'  ✓ Created {invoice_count} invoices')
            self.stdout.write(f'  ✓ Created {payment_count} payments')
            
            # 8. Create Expenses
            expense_count = 0
            
            exp1 = Expense.objects.create(
                building=building,
                category=categories[0],  # صيانة
                amount=Decimal('250.00'),
                expense_date=datetime.date(2026, 1, 12),
                description="إصلاح مصعد",
                vendor_name="شركة المصاعد"
            )
            AccountingService.process_expense_ledger(exp1)
            expense_count += 1
            
            exp2 = Expense.objects.create(
                building=building,
                category=categories[1],  # كهرباء
                amount=Decimal('180.00'),
                expense_date=datetime.date(2026, 1, 20),
                description="فاتورة كهرباء يناير",
                vendor_name="شركة الكهرباء الوطنية"
            )
            AccountingService.process_expense_ledger(exp2)
            expense_count += 1
            
            exp3 = Expense.objects.create(
                building=building,
                category=categories[2],  # نظافة
                amount=Decimal('120.00'),
                expense_date=datetime.date(2026, 1, 25),
                description="تنظيف المبنى",
                vendor_name="شركة النظافة المتقدمة"
            )
            AccountingService.process_expense_ledger(exp3)
            expense_count += 1
            
            self.stdout.write(f'  ✓ Created {expense_count} expenses')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Dummy data created successfully!'))
        self.stdout.write(self.style.SUCCESS('\n📊 Summary:'))
        self.stdout.write(f'  • 1 Building')
        self.stdout.write(f'  • 2 Floors')
        self.stdout.write(f'  • 3 Units')
        self.stdout.write(f'  • 2 Tenants')
        self.stdout.write(f'  • 2 Contracts')
        self.stdout.write(f'  • {len(categories)} Expense Categories')
        self.stdout.write(f'  • {invoice_count} Invoices')
        self.stdout.write(f'  • {payment_count} Payments')
        self.stdout.write(f'  • {expense_count} Expenses')
        self.stdout.write(f'  • {LedgerEntry.objects.count()} Ledger Entries')
        self.stdout.write(self.style.SUCCESS('\n✨ Ready for testing!'))
