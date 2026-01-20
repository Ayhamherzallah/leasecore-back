from django.core.management.base import BaseCommand
from django.db import transaction
from billing.models import Invoice


class Command(BaseCommand):
    help = 'Delete knowledge tax invoices that have no linked contract'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find knowledge tax invoices without a contract
        orphaned_invoices = Invoice.objects.filter(
            knowledge_tax_amount__gt=0,
            contract__isnull=True
        )
        
        count = orphaned_invoices.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No orphaned knowledge tax invoices found.'))
            return
        
        self.stdout.write(f'Found {count} orphaned knowledge tax invoice(s):')
        
        for inv in orphaned_invoices:
            self.stdout.write(f'  - {inv.invoice_number}: {inv.tenant.name if inv.tenant else "No Tenant"} - {inv.knowledge_tax_amount} JOD - {inv.issue_date}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No invoices were deleted.'))
            return
        
        # Delete the orphaned invoices (with related payments via CASCADE or manual cleanup)
        with transaction.atomic():
            # First, delete related payments
            from billing.models import Payment
            payments_deleted = 0
            for inv in orphaned_invoices:
                payment_count = inv.payments.count()
                inv.payments.all().delete()
                payments_deleted += payment_count
            
            # Then delete the invoices
            deleted_count, _ = orphaned_invoices.delete()
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully deleted {deleted_count} orphaned knowledge tax invoice(s) and {payments_deleted} related payment(s).'
            ))

