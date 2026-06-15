from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def backfill_line_items(apps, schema_editor):
    Invoice = apps.get_model('billing', 'Invoice')
    InvoiceLineItem = apps.get_model('billing', 'InvoiceLineItem')
    for invoice in Invoice.objects.all():
        if invoice.line_items.exists():
            continue
        tax = invoice.knowledge_tax_amount or Decimal('0')
        line_amount = (invoice.total_amount or Decimal('0')) - tax
        if line_amount < 0:
            line_amount = invoice.total_amount or Decimal('0')
        description = (invoice.description or '').strip() or invoice.invoice_type or 'Invoice'
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description=description,
            quantity=Decimal('1'),
            unit_price=line_amount,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0009_payment_paid_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='notes',
            field=models.TextField(blank=True, help_text='Notes or payment terms shown on the invoice'),
        ),
        migrations.CreateModel(
            name='InvoiceLineItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=500)),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=12)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('invoice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='line_items', to='billing.invoice')),
            ],
            options={
                'ordering': ['sort_order', 'id'],
            },
        ),
        migrations.RunPython(backfill_line_items, migrations.RunPython.noop),
    ]
