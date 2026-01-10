from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from .models import Building, Floor, Unit
from .serializers import BuildingSerializer, FloorSerializer, UnitSerializer

class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all()
    serializer_class = BuildingSerializer
    permission_classes = []

class FloorViewSet(viewsets.ModelViewSet):
    queryset = Floor.objects.all().order_by('number')
    serializer_class = FloorSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['building']

class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all().order_by('unit_number')
    serializer_class = UnitSerializer
    permission_classes = []
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['floor', 'floor__building', 'status']
