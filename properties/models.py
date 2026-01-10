from django.db import models
from django.utils.translation import gettext_lazy as _

class Building(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    total_area = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total square meters")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"

    def __str__(self):
        return self.name

class Floor(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='floors')
    name = models.CharField(max_length=50, help_text="e.g. Ground Floor, Floor 1")
    number = models.IntegerField(help_text="For sorting purposes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['number']
        indexes = [
            models.Index(fields=['building', 'number']),
        ]

    def __str__(self):
        return f"{self.building.name} - {self.name}"

class Unit(models.Model):
    class UnitType(models.TextChoices):
        RESIDENTIAL = 'RESIDENTIAL', _('Residential')
        COMMERCIAL = 'COMMERCIAL', _('Commercial')
        RETAIL = 'RETAIL', _('Retail')

    class UnitStatus(models.TextChoices):
        VACANT = 'VACANT', _('Vacant')
        OCCUPIED = 'OCCUPIED', _('Occupied')
        MAINTENANCE = 'MAINTENANCE', _('Under Maintenance')
        RESERVED = 'RESERVED', _('Reserved')

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name='units')
    unit_number = models.CharField(max_length=50)
    unit_type = models.CharField(max_length=20, choices=UnitType.choices, default=UnitType.RESIDENTIAL)
    status = models.CharField(max_length=20, choices=UnitStatus.choices, default=UnitStatus.VACANT, db_index=True)
    area = models.DecimalField(max_digits=10, decimal_places=2, help_text="Square meters")
    
    # Financial reference
    market_rent = models.DecimalField(max_digits=12, decimal_places=2, help_text="Target rental price")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit_number']
        unique_together = ['floor', 'unit_number']

    def __str__(self):
        return f"{self.unit_number} ({self.status})"
