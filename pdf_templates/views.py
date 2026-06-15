from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse

from users.building_access import user_can_access_building
from users.permissions import CanManageBuildingOperations
from users.utils import is_platform_admin

from .models import PdfBrandingProfile
from .serializers import PdfBrandingProfileSerializer, serialize_template_list
from .engine.branding import get_or_create_branding_profile
from .engine.generators import generate_sample_pdf
from .engine.theme import PdfTheme
from .engine.fonts import register_pdf_fonts


class PdfBrandingViewSet(viewsets.ModelViewSet):
    """Manage PDF template & branding settings per building."""
    serializer_class = PdfBrandingProfileSerializer
    permission_classes = [IsAuthenticated, CanManageBuildingOperations]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def get_queryset(self):
        from users.building_access import get_accessible_building_ids
        user = self.request.user
        if is_platform_admin(user):
            return PdfBrandingProfile.objects.select_related('building').all()
        ids = get_accessible_building_ids(user)
        return PdfBrandingProfile.objects.select_related('building').filter(building_id__in=ids)

    def list(self, request, *args, **kwargs):
        building_id = request.query_params.get('building')
        if building_id:
            if not user_can_access_building(request.user, building_id):
                return Response({'detail': 'No access to this building.'}, status=403)
            profile = get_or_create_branding_profile(building_id)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        building_id = request.data.get('building')
        if not building_id:
            return Response({'building': 'Required.'}, status=400)
        if not user_can_access_building(request.user, building_id):
            return Response({'detail': 'No access to this building.'}, status=403)
        profile = get_or_create_branding_profile(building_id)
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    @action(detail=False, methods=['get'], url_path='templates')
    def templates(self, request):
        return Response(serialize_template_list())

    @action(detail=False, methods=['get'], url_path='preview', permission_classes=[IsAuthenticated])
    def preview(self, request):
        building_id = request.query_params.get('building')
        if building_id and not user_can_access_building(request.user, building_id):
            return Response({'detail': 'No access.'}, status=403)

        template_id = request.query_params.get('template')
        theme = None

        if building_id:
            profile = get_or_create_branding_profile(building_id)
            if template_id:
                profile.template = template_id
            for field in ('primary_color', 'secondary_color', 'accent_color'):
                val = request.query_params.get(field)
                if val:
                    setattr(profile, field, val)
            theme = PdfTheme.from_profile(profile, register_pdf_fonts())
            if not theme.logo_path and not theme.logo_reader:
                from .engine.branding import _default_logo_path
                theme.logo_path = _default_logo_path()
        elif template_id:
            from properties.models import Building
            building = None
            theme = PdfTheme.preset(template_id, building, register_pdf_fonts())
        else:
            from .engine.branding import resolve_theme
            theme = resolve_theme(building_id)

        lang = request.query_params.get('lang', 'en')
        buffer = generate_sample_pdf(theme=theme, building_id=building_id, lang=lang)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="pdf-preview.pdf"'
        return response
