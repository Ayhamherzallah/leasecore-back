from rest_framework import serializers
from django.contrib.auth.models import User
from .models import UserProfile, Role

class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='profile.role', required=False)
    full_name = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'password', 'role', 'full_name']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True}
        }
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        role = profile_data.get('role', Role.MANAGER)
        password = validated_data.pop('password')
        
        user = User.objects.create_user(**validated_data, password=password)
        
        # Profile is created via signals, so we just update it
        if hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
            
        return user

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        role = profile_data.get('role')
        
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if role and hasattr(instance, 'profile'):
            instance.profile.role = role
            instance.profile.save()
            
        return instance
