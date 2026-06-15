# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='buildings',
            field=models.ManyToManyField(blank=True, related_name='assigned_users', to='properties.building'),
        ),
    ]
