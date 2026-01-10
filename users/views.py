from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import UserProfile
from .serializers import UserSerializer
from .permissions import IsSuperAdmin

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    user = request.user
    role = 'MANAGER' # Default fallback
    if hasattr(user, 'profile'):
        role = user.profile.role
    
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': f"{user.first_name} {user.last_name}".strip(),
        'role': role
    })

class UserViewSet(viewsets.ModelViewSet):
    """
    User management ViewSet.
    Only SUPER_ADMIN can access this.
    """
    queryset = User.objects.all().select_related('profile').order_by('id')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
