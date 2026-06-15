from rest_framework import serializers
from django.contrib.auth.models import User
from properties.models import Building
from .models import UserProfile, Role


class BuildingBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'name', 'address']


BUILDING_SCOPED_ROLES = (
    Role.MANAGER,
    Role.ACCOUNTANT,
    Role.BUILDING_MANAGER,
)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', required=False)
    building_ids = serializers.PrimaryKeyRelatedField(
        queryset=Building.objects.all(),
        many=True,
        source='profile.buildings',
        required=False,
    )
    buildings = BuildingBriefSerializer(source='profile.buildings', many=True, read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 'is_active',
            'password', 'role', 'building_ids', 'buildings', 'full_name',
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
        }

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def validate(self, attrs):
        profile_data = attrs.get('profile', {})
        role = profile_data.get('role')
        buildings = profile_data.get('buildings')

        if role == Role.SUPER_ADMIN:
            profile_data['buildings'] = []
        elif role in BUILDING_SCOPED_ROLES:
            if role == Role.BUILDING_MANAGER and buildings is not None and len(buildings) == 0:
                raise serializers.ValidationError({
                    'building_ids': 'Building managers must be assigned to at least one building.',
                })
        return attrs

    def _save_profile(self, user, profile_data):
        role = profile_data.get('role')
        buildings = profile_data.get('buildings')

        if not hasattr(user, 'profile'):
            return

        if role:
            user.profile.role = role

        user.profile.save()

        if buildings is not None:
            user.profile.buildings.set(buildings)

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        role = profile_data.get('role', Role.BUILDING_MANAGER)
        buildings = profile_data.get('buildings')
        password = validated_data.pop('password')

        if role == Role.BUILDING_MANAGER and not buildings:
            raise serializers.ValidationError({
                'building_ids': 'Building managers must be assigned to at least one building.',
            })

        user = User.objects.create_user(**validated_data, password=password)

        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
            if buildings is not None:
                user.profile.buildings.set(buildings)

        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        password = validated_data.pop('password', None)

        if password:
            instance.set_password(password)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        self._save_profile(instance, profile_data)
        return instance
