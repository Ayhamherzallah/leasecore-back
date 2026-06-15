from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_building_access'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='role',
            field=models.CharField(
                choices=[
                    ('SUPER_ADMIN', 'Super Admin'),
                    ('BUILDING_MANAGER', 'Building Manager'),
                    ('ACCOUNTANT', 'Accountant'),
                    ('MANAGER', 'Manager'),
                ],
                default='BUILDING_MANAGER',
                max_length=20,
            ),
        ),
    ]
