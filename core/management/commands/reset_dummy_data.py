from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from decimal import Decimal
import datetime
import random

from properties.models import Building, Floor, Unit
from tenants.models import Tenant, Contract
from billing.models import Invoice, Payment, Cheque
from expenses.models import ExpenseCategory, Expense
from accounting.models import LedgerEntry
from accounting.services import AccountingService
from users.models import UserProfile


class Command(BaseCommand):
    help = 'Clear all data and create comprehensive dummy data for testing'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')

    def handle(self, *args, **kwargs):
        if not kwargs.get('confirm'):
            self.stdout.write(self.style.WARNING('This will DELETE ALL DATA!'))
            confirm = input('Type "yes" to continue: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Cancelled'))
                return

        self.stdout.write('Clearing all data...')
        LedgerEntry.objects.all().delete()
        Cheque.objects.all().delete()
        Payment.objects.all().delete()
        Expense.objects.all().delete()
        Invoice.objects.all().delete()
        Contract.objects.all().delete()
        Tenant.objects.all().delete()
        Unit.objects.all().delete()
        Floor.objects.all().delete()
        Building.objects.all().delete()
        ExpenseCategory.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Data cleared'))
        self.stdout.write('Creating dummy data...')

        with transaction.atomic():
            self._create_users()
            buildings = self._create_properties()
            tenants = self._create_tenants()
            contracts = self._create_contracts(buildings, tenants)
            categories = self._create_expense_categories()
            self._create_invoices_and_payments(contracts, buildings)
            self._create_expenses(buildings, categories)

        self.stdout.write(self.style.SUCCESS('\nDone! Summary:'))
        self.stdout.write(f'  Buildings: {Building.objects.count()}')
        self.stdout.write(f'  Floors: {Floor.objects.count()}')
        self.stdout.write(f'  Units: {Unit.objects.count()}')
        self.stdout.write(f'  Tenants: {Tenant.objects.count()}')
        self.stdout.write(f'  Contracts: {Contract.objects.count()}')
        self.stdout.write(f'  Invoices: {Invoice.objects.count()}')
        self.stdout.write(f'  Payments: {Payment.objects.count()}')
        self.stdout.write(f'  Cheques: {Cheque.objects.count()}')
        self.stdout.write(f'  Expenses: {Expense.objects.count()}')
        self.stdout.write(f'  Ledger Entries: {LedgerEntry.objects.count()}')

    def _create_users(self):
        users_data = [
            ('admin', 'admin@leasecore.app', 'Admin', 'User', 'SUPER_ADMIN'),
            ('accountant', 'accountant@leasecore.app', 'Ahmad', 'Nasser', 'ACCOUNTANT'),
            ('manager', 'manager@leasecore.app', 'Rami', 'Haddad', 'MANAGER'),
        ]
        for username, email, first, last, role in users_data:
            user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'first_name': first, 'last_name': last})
            if created:
                user.set_password('pass1234')
                user.save()
            UserProfile.objects.update_or_create(user=user, defaults={'role': role})
        self.stdout.write(f'  Users: {len(users_data)}')

    def _create_properties(self):
        buildings_data = [
            ('Al Safa Plaza', 'King Abdullah II Street, Amman', Decimal('2400.00'), [
                ('Ground Floor', 0, [
                    ('G01', 'COMMERCIAL', Decimal('120.00'), Decimal('1800.00')),
                    ('G02', 'COMMERCIAL', Decimal('95.00'), Decimal('1500.00')),
                    ('G03', 'RETAIL', Decimal('60.00'), Decimal('1200.00')),
                    ('G04', 'RETAIL', Decimal('55.00'), Decimal('1100.00')),
                ]),
                ('1st Floor', 1, [
                    ('101', 'COMMERCIAL', Decimal('110.00'), Decimal('1400.00')),
                    ('102', 'COMMERCIAL', Decimal('100.00'), Decimal('1300.00')),
                    ('103', 'COMMERCIAL', Decimal('85.00'), Decimal('1100.00')),
                ]),
                ('2nd Floor', 2, [
                    ('201', 'RESIDENTIAL', Decimal('130.00'), Decimal('900.00')),
                    ('202', 'RESIDENTIAL', Decimal('120.00'), Decimal('850.00')),
                    ('203', 'RESIDENTIAL', Decimal('100.00'), Decimal('750.00')),
                ]),
                ('3rd Floor', 3, [
                    ('301', 'RESIDENTIAL', Decimal('130.00'), Decimal('950.00')),
                    ('302', 'RESIDENTIAL', Decimal('120.00'), Decimal('880.00')),
                ]),
            ]),
            ('Al Noor Tower', 'Mecca Street, Amman', Decimal('1800.00'), [
                ('Ground Floor', 0, [
                    ('G01', 'RETAIL', Decimal('80.00'), Decimal('2000.00')),
                    ('G02', 'RETAIL', Decimal('70.00'), Decimal('1800.00')),
                ]),
                ('1st Floor', 1, [
                    ('101', 'COMMERCIAL', Decimal('150.00'), Decimal('1600.00')),
                    ('102', 'COMMERCIAL', Decimal('140.00'), Decimal('1500.00')),
                ]),
                ('2nd Floor', 2, [
                    ('201', 'COMMERCIAL', Decimal('130.00'), Decimal('1400.00')),
                    ('202', 'COMMERCIAL', Decimal('120.00'), Decimal('1300.00')),
                ]),
            ]),
        ]

        buildings = []
        for b_name, b_addr, b_area, floors_data in buildings_data:
            building = Building.objects.create(name=b_name, address=b_addr, total_area=b_area)
            for f_name, f_num, units_data in floors_data:
                floor = Floor.objects.create(building=building, name=f_name, number=f_num)
                for u_num, u_type, u_area, u_rent in units_data:
                    Unit.objects.create(floor=floor, unit_number=u_num, unit_type=u_type, area=u_area, market_rent=u_rent, status='VACANT')
            buildings.append(building)

        self.stdout.write(f'  Buildings: {len(buildings)}, Units: {Unit.objects.count()}')
        return buildings

    def _create_tenants(self):
        tenants_data = [
            ('Gulf Trading Co.', 'COMPANY', 'gulf@trading.jo', '+962791001001', '2345678901', 'JO-TAX-001'),
            ('Al Noor Textiles', 'COMPANY', 'info@alnoor.jo', '+962791002002', '3456789012', 'JO-TAX-002'),
            ('Crescent Motors', 'COMPANY', 'admin@crescent.jo', '+962791003003', '4567890123', 'JO-TAX-003'),
            ('Oasis Electronics', 'COMPANY', 'sales@oasis.jo', '+962791004004', '5678901234', 'JO-TAX-004'),
            ('Mohammad Al-Rashid', 'INDIVIDUAL', 'mohammad@email.com', '+962791005005', '9876543210', ''),
            ('Sara Hammad', 'INDIVIDUAL', 'sara@email.com', '+962791006006', '8765432109', ''),
            ('Khalil Abu Zeid', 'INDIVIDUAL', 'khalil@email.com', '+962791007007', '7654321098', ''),
            ('Layla Mansour', 'INDIVIDUAL', 'layla@email.com', '+962791008008', '6543210987', ''),
            ('Petra Pharmacy', 'COMPANY', 'info@petrapharm.jo', '+962791009009', '1234509876', 'JO-TAX-005'),
            ('Amman Coffee House', 'COMPANY', 'hello@ammancoffee.jo', '+962791010010', '9012345678', 'JO-TAX-006'),
        ]

        tenants = []
        for name, t_type, email, phone, nid, tax in tenants_data:
            t = Tenant.objects.create(name=name, tenant_type=t_type, email=email, phone=phone, national_id=nid, tax_number=tax)
            tenants.append(t)

        self.stdout.write(f'  Tenants: {len(tenants)}')
        return tenants

    def _create_contracts(self, buildings, tenants):
        all_units = list(Unit.objects.all())
        contracts = []

        assignments = [
            (0, tenants[0], Decimal('1800.00'), 'MONTHLY', 'ACTIVE'),
            (1, tenants[1], Decimal('1500.00'), 'MONTHLY', 'ACTIVE'),
            (2, tenants[8], Decimal('1200.00'), 'MONTHLY', 'ACTIVE'),
            (4, tenants[2], Decimal('1400.00'), 'MONTHLY', 'ACTIVE'),
            (5, tenants[3], Decimal('1300.00'), 'MONTHLY', 'ACTIVE'),
            (7, tenants[4], Decimal('900.00'), 'MONTHLY', 'ACTIVE'),
            (8, tenants[5], Decimal('850.00'), 'MONTHLY', 'ACTIVE'),
            (10, tenants[6], Decimal('950.00'), 'MONTHLY', 'ACTIVE'),
            (12, tenants[9], Decimal('2000.00'), 'MONTHLY', 'ACTIVE'),
            (14, tenants[7], Decimal('1600.00'), 'QUARTERLY', 'ACTIVE'),
        ]

        start = datetime.date(2025, 7, 1)
        end = datetime.date(2026, 6, 30)

        for unit_idx, tenant, rent, freq, status in assignments:
            if unit_idx < len(all_units):
                unit = all_units[unit_idx]
                c = Contract.objects.create(
                    tenant=tenant, unit=unit, start_date=start, end_date=end,
                    rent_amount=rent, payment_frequency=freq, status=status,
                    security_deposit=rent,
                )
                unit.status = 'OCCUPIED'
                unit.save()
                contracts.append(c)

        self.stdout.write(f'  Contracts: {len(contracts)}')
        return contracts

    def _create_invoices_and_payments(self, contracts, buildings):
        inv_count = 0
        pay_count = 0
        chq_count = 0
        today = datetime.date.today()

        for contract in contracts:
            building = contract.unit.floor.building
            current = contract.start_date
            month_num = 0

            while current <= today and current < contract.end_date:
                month_num += 1
                due = current + datetime.timedelta(days=30)
                inv = Invoice.objects.create(
                    contract=contract, tenant=contract.tenant,
                    issue_date=current, due_date=due,
                    total_amount=contract.rent_amount,
                    invoice_type='RENT', status='ISSUED',
                    knowledge_tax_amount=contract.rent_amount * Decimal('0.02'),
                )
                AccountingService.process_invoice_ledger(inv)
                inv_count += 1

                months_ago = (today.year - current.year) * 12 + (today.month - current.month)

                if months_ago >= 2:
                    method = random.choice(['CASH', 'TRANSFER', 'CHECK'])
                    pay_date = current + datetime.timedelta(days=random.randint(3, 20))
                    pay = Payment.objects.create(
                        invoice=inv, amount=contract.rent_amount,
                        payment_date=pay_date, payment_method=method,
                    )
                    inv.paid_amount = contract.rent_amount
                    inv.status = 'PAID'
                    inv.save()
                    AccountingService.process_payment_ledger(pay)
                    pay_count += 1

                    if method == 'CHECK':
                        banks = ['Arab Bank', 'Housing Bank', 'Jordan Ahli Bank', 'Cairo Amman Bank']
                        Cheque.objects.create(
                            payment=pay, cheque_number=f'CHQ-{random.randint(10000,99999)}',
                            bank_name=random.choice(banks), drawer_name=contract.tenant.name,
                            amount=contract.rent_amount, cheque_date=pay_date,
                            status=random.choice(['CLEARED', 'DEPOSITED']),
                            cleared_date=pay_date + datetime.timedelta(days=random.randint(3, 10)) if random.random() > 0.3 else None,
                        )
                        chq_count += 1

                elif months_ago == 1:
                    partial = contract.rent_amount * Decimal('0.5')
                    pay = Payment.objects.create(
                        invoice=inv, amount=partial,
                        payment_date=current + datetime.timedelta(days=10),
                        payment_method='CASH',
                    )
                    inv.paid_amount = partial
                    inv.status = 'PARTIALLY_PAID'
                    inv.save()
                    AccountingService.process_payment_ledger(pay)
                    pay_count += 1

                if contract.payment_frequency == 'MONTHLY':
                    month = current.month + 1
                    year = current.year
                    if month > 12:
                        month = 1
                        year += 1
                    current = current.replace(year=year, month=month)
                else:
                    current += datetime.timedelta(days=90)

        self.stdout.write(f'  Invoices: {inv_count}, Payments: {pay_count}, Cheques: {chq_count}')

    def _create_expense_categories(self):
        cats = [
            ('Maintenance', 'Repairs and maintenance work'),
            ('Electricity', 'Electricity bills'),
            ('Water', 'Water supply bills'),
            ('Cleaning', 'Cleaning services'),
            ('Security', 'Security services'),
            ('Insurance', 'Building insurance'),
            ('Elevator', 'Elevator maintenance and service'),
        ]
        result = []
        for name, desc in cats:
            obj, _ = ExpenseCategory.objects.get_or_create(name=name, defaults={'description': desc})
            result.append(obj)
        self.stdout.write(f'  Expense Categories: {len(result)}')
        return result

    def _create_expenses(self, buildings, categories):
        count = 0
        today = datetime.date.today()
        vendors = {
            'Maintenance': ['Fix-It Services', 'ProBuild Maintenance'],
            'Electricity': ['Jordan Electric Power Co.'],
            'Water': ['Miyahuna Water Co.'],
            'Cleaning': ['SparkClean Services', 'Fresh & Clean Co.'],
            'Security': ['SafeGuard Security'],
            'Insurance': ['Arabia Insurance Co.'],
            'Elevator': ['Schindler Jordan', 'KONE Elevators'],
        }

        expenses_data = [
            (0, 'Maintenance', 'Elevator annual service', Decimal('450.00'), datetime.date(2025, 8, 15)),
            (0, 'Electricity', 'Common area electricity - Aug', Decimal('320.00'), datetime.date(2025, 8, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Aug', Decimal('180.00'), datetime.date(2025, 8, 25)),
            (0, 'Electricity', 'Common area electricity - Sep', Decimal('290.00'), datetime.date(2025, 9, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Sep', Decimal('180.00'), datetime.date(2025, 9, 25)),
            (0, 'Water', 'Water bill - Q3', Decimal('210.00'), datetime.date(2025, 9, 30)),
            (0, 'Maintenance', 'Plumbing repair - 2nd floor', Decimal('175.00'), datetime.date(2025, 10, 8)),
            (0, 'Electricity', 'Common area electricity - Oct', Decimal('310.00'), datetime.date(2025, 10, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Oct', Decimal('180.00'), datetime.date(2025, 10, 25)),
            (0, 'Security', 'Security system upgrade', Decimal('800.00'), datetime.date(2025, 11, 5)),
            (0, 'Electricity', 'Common area electricity - Nov', Decimal('340.00'), datetime.date(2025, 11, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Nov', Decimal('180.00'), datetime.date(2025, 11, 25)),
            (0, 'Insurance', 'Annual building insurance', Decimal('2400.00'), datetime.date(2025, 12, 1)),
            (0, 'Electricity', 'Common area electricity - Dec', Decimal('360.00'), datetime.date(2025, 12, 20)),
            (0, 'Maintenance', 'Roof waterproofing', Decimal('1200.00'), datetime.date(2025, 12, 28)),
            (0, 'Electricity', 'Common area electricity - Jan', Decimal('380.00'), datetime.date(2026, 1, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Jan', Decimal('180.00'), datetime.date(2026, 1, 25)),
            (0, 'Elevator', 'Elevator emergency repair', Decimal('650.00'), datetime.date(2026, 2, 3)),
            (0, 'Electricity', 'Common area electricity - Feb', Decimal('330.00'), datetime.date(2026, 2, 20)),
            (0, 'Cleaning', 'Monthly cleaning service - Feb', Decimal('180.00'), datetime.date(2026, 2, 25)),
            (0, 'Water', 'Water bill - Q4', Decimal('240.00'), datetime.date(2026, 3, 1)),
            (0, 'Maintenance', 'Parking lot repaint', Decimal('550.00'), datetime.date(2026, 3, 10)),
            (0, 'Electricity', 'Common area electricity - Mar', Decimal('300.00'), datetime.date(2026, 3, 20)),
            (1, 'Electricity', 'Common area electricity - Jan', Decimal('220.00'), datetime.date(2026, 1, 20)),
            (1, 'Cleaning', 'Monthly cleaning - Jan', Decimal('150.00'), datetime.date(2026, 1, 25)),
            (1, 'Maintenance', 'HVAC maintenance', Decimal('380.00'), datetime.date(2026, 2, 10)),
            (1, 'Electricity', 'Common area electricity - Feb', Decimal('210.00'), datetime.date(2026, 2, 20)),
            (1, 'Cleaning', 'Monthly cleaning - Feb', Decimal('150.00'), datetime.date(2026, 2, 25)),
            (1, 'Electricity', 'Common area electricity - Mar', Decimal('200.00'), datetime.date(2026, 3, 20)),
        ]

        cat_map = {c.name: c for c in categories}
        for b_idx, cat_name, desc, amount, date in expenses_data:
            if date <= today and b_idx < len(buildings):
                vendor_list = vendors.get(cat_name, ['General Vendor'])
                exp = Expense.objects.create(
                    building=buildings[b_idx], category=cat_map[cat_name],
                    description=desc, amount=amount, expense_date=date,
                    vendor_name=random.choice(vendor_list),
                )
                AccountingService.process_expense_ledger(exp)
                count += 1

        self.stdout.write(f'  Expenses: {count}')
