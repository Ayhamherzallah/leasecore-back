from django.contrib import admin
from .models import PdfBrandingProfile


@admin.register(PdfBrandingProfile)
class PdfBrandingProfileAdmin(admin.ModelAdmin):
    list_display = ('building', 'template', 'primary_color', 'updated_at')
    list_filter = ('template',)
