from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Role
from .serializers import UserSerializer, BuildingBriefSerializer
from .permissions import IsSuperAdmin
from .utils import ensure_user_profile, is_platform_admin, get_user_role, get_accessible_buildings


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    ensure_user_profile(request.user)
    role = get_user_role(request.user)
    buildings = get_accessible_buildings(request.user)

    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'full_name': f"{request.user.first_name} {request.user.last_name}".strip(),
        'role': role,
        'is_platform_admin': is_platform_admin(request.user),
        'buildings': BuildingBriefSerializer(buildings, many=True).data,
    })


class UserViewSet(viewsets.ModelViewSet):
    """
    User management ViewSet.
    Only platform admins (SUPER_ADMIN) can access this.
    """
    queryset = User.objects.all().select_related('profile').prefetch_related('profile__buildings').order_by('id')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        user_type = self.request.query_params.get('type')
        if user_type == 'vendor':
            qs = qs.filter(profile__role__in=[Role.MANAGER, Role.ACCOUNTANT, Role.BUILDING_MANAGER])
        elif user_type == 'admin':
            qs = qs.filter(profile__role=Role.SUPER_ADMIN)
        return qs

    def perform_create(self, serializer):
        user = serializer.save()
        ensure_user_profile(user)

    def perform_update(self, serializer):
        user = serializer.save()
        ensure_user_profile(user)
