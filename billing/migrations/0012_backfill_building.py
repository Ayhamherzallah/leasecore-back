from django.db import migrations


def backfill_building(apps, schema_editor):
    Tenant = apps.get_model('tenants', 'Tenant')
    Contract = apps.get_model('tenants', 'Contract')
    Invoice = apps.get_model('billing', 'Invoice')

    # 1. Tenant.building <- first contract's building (if any)
    for tenant in Tenant.objects.all().iterator():
        contract = (
            Contract.objects
            .filter(tenant_id=tenant.id)
            .select_related('unit', 'unit__floor')
            .first()
        )
        if contract and contract.unit and contract.unit.floor_id:
            building_id = contract.unit.floor.building_id
            if building_id and tenant.building_id != building_id:
                tenant.building_id = building_id
                tenant.save(update_fields=['building_id'])

    # 2. Invoice.building <- contract building, else tenant building
    for invoice in Invoice.objects.select_related(
        'contract', 'contract__unit', 'contract__unit__floor', 'tenant'
    ).iterator():
        building_id = None
        if invoice.contract and invoice.contract.unit and invoice.contract.unit.floor_id:
            building_id = invoice.contract.unit.floor.building_id
        elif invoice.tenant_id:
            building_id = invoice.tenant.building_id
        if building_id and invoice.building_id != building_id:
            invoice.building_id = building_id
            invoice.save(update_fields=['building_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0011_invoice_building'),
        ('tenants', '0004_tenant_building'),
    ]

    operations = [
        migrations.RunPython(backfill_building, noop),
    ]
