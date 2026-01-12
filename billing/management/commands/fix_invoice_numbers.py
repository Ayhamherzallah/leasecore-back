from django.core.management.base import BaseCommand
from billing.models import Invoice

class Command(BaseCommand):
    help = 'Fix missing or invalid invoice numbers'

    def handle(self, *args, **options):
        # Filter for likely invalid numbers
        # Note: 'unique=True' constraint means there shouldn't be multiple empty strings in strict DBs,
        # but valid numbers might be missing if imported or created directly.
        
        # We check for empty, or short, or non-compliant numbers if needed.
        # Here we focus on empty/null.
        
        invoices = Invoice.objects.all()
        updated_count = 0
        
        for inv in invoices:
            current_num = str(inv.invoice_number).strip()
            
            # Criteria for "bad": Empty, None, or just "#"
            is_bad = (not current_num) or (current_num == '#') or (current_num == 'None')
            
            if is_bad:
                self.stdout.write(f"Found bad invoice number for ID {inv.id}: '{inv.invoice_number}'")
                
                # Clear it so model.save() generates a new one
                inv.invoice_number = ''
                inv.save()
                
                self.stdout.write(f" -> Assigned new number: {inv.invoice_number}")
                updated_count += 1
                
        self.stdout.write(self.style.SUCCESS(f'Successfully checked all invoices. Fixed {updated_count} issues.'))
