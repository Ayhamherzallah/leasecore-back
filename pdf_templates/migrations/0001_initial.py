from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('properties', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PdfBrandingProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('template', models.CharField(
                    choices=[
                        ('modern', 'Modern'),
                        ('classic', 'Classic'),
                        ('minimal', 'Minimal'),
                        ('corporate', 'Corporate'),
                    ],
                    default='modern',
                    max_length=20,
                )),
                ('logo', models.ImageField(blank=True, null=True, upload_to='pdf_logos/')),
                ('primary_color', models.CharField(default='#5bb5a2', max_length=7)),
                ('secondary_color', models.CharField(default='#1e2d3d', max_length=7)),
                ('accent_color', models.CharField(default='#4a9e8d', max_length=7)),
                ('company_name_en', models.CharField(blank=True, default='', max_length=255)),
                ('company_name_ar', models.CharField(blank=True, default='', max_length=255)),
                ('company_address_en', models.TextField(blank=True, default='')),
                ('company_address_ar', models.TextField(blank=True, default='')),
                ('footer_text', models.CharField(blank=True, default='', max_length=500)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('building', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='pdf_branding',
                    to='properties.building',
                )),
            ],
            options={
                'verbose_name': 'PDF Branding Profile',
            },
        ),
    ]
