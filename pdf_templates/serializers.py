from rest_framework import serializers
from .models import PdfBrandingProfile
from .template_registry import PDF_TEMPLATES


class PdfTemplateListSerializer(serializers.Serializer):
    id = serializers.CharField()
    name_en = serializers.CharField()
    name_ar = serializers.CharField()
    description_en = serializers.CharField()
    description_ar = serializers.CharField()
    layout = serializers.CharField()


class PdfBrandingProfileSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()
    building_name = serializers.CharField(source='building.name', read_only=True)

    class Meta:
        model = PdfBrandingProfile
        fields = [
            'id', 'building', 'building_name', 'template',
            'logo', 'logo_url',
            'primary_color', 'secondary_color', 'accent_color',
            'company_name_en', 'company_name_ar',
            'company_address_en', 'company_address_ar',
            'footer_text', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at', 'logo_url', 'building_name']

    def get_logo_url(self, obj):
        if obj.logo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.logo.url)
            return obj.logo.url
        return None

    def validate_primary_color(self, value):
        return self._validate_hex(value)

    def validate_secondary_color(self, value):
        return self._validate_hex(value)

    def validate_accent_color(self, value):
        return self._validate_hex(value)

    def _validate_hex(self, value):
        if not value.startswith('#') or len(value) not in (4, 7):
            raise serializers.ValidationError('Must be a valid hex color (e.g. #5bb5a2).')
        return value


def serialize_template_list():
    return PDF_TEMPLATES
