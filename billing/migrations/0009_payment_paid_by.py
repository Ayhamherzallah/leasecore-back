from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0008_invoice_knowledge_tax_amount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='paid_by',
            field=models.CharField(
                blank=True,
                help_text='Name or identity of the person who made the payment',
                max_length=200,
            ),
        ),
    ]
