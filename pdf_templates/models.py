from django.db import models
from .template_registry import TEMPLATE_MODERN, PDF_TEMPLATE_CHOICES


class PdfBrandingProfile(models.Model):
    """Per-building PDF branding — logo, colors, and template style."""

    building = models.OneToOneField(
        'properties.Building',
        on_delete=models.CASCADE,
        related_name='pdf_branding',
    )
    template = models.CharField(
        max_length=20,
        choices=PDF_TEMPLATE_CHOICES,
        default=TEMPLATE_MODERN,
    )
    logo = models.ImageField(upload_to='pdf_logos/', blank=True, null=True)

    primary_color = models.CharField(max_length=7, default='#5bb5a2')
    secondary_color = models.CharField(max_length=7, default='#1e2d3d')
    accent_color = models.CharField(max_length=7, default='#4a9e8d')

    company_name_en = models.CharField(max_length=255, blank=True, default='')
    company_name_ar = models.CharField(max_length=255, blank=True, default='')
    company_address_en = models.TextField(blank=True, default='')
    company_address_ar = models.TextField(blank=True, default='')
    footer_text = models.CharField(max_length=500, blank=True, default='')

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'PDF Branding Profile'

    def __str__(self):
        return f'PDF branding — {self.building.name}'

    def save(self, *args, **kwargs):
        if not self.company_name_en and self.building_id:
            self.company_name_en = self.building.name
        if not self.company_name_ar and self.building_id:
            self.company_name_ar = self.building.name
        if not self.company_address_en and self.building_id:
            self.company_address_en = self.building.address or ''
        if not self.company_address_ar and self.building_id:
            self.company_address_ar = self.building.address or ''
        super().save(*args, **kwargs)
