from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from users.models import Role, UserProfile
from users.utils import ensure_user_profile


class Command(BaseCommand):
    help = 'Sync Django superusers into Platform Admin profiles (SUPER_ADMIN role)'

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.all():
            before = getattr(getattr(user, 'profile', None), 'role', None)
            ensure_user_profile(user)
            user.refresh_from_db()
            after = user.profile.role
            if before != after or user.is_superuser:
                count += 1
                self.stdout.write(f'  {user.username}: {after}')

        superusers = User.objects.filter(is_superuser=True)
        for user in superusers:
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': Role.SUPER_ADMIN})
            if profile.role != Role.SUPER_ADMIN:
                profile.role = Role.SUPER_ADMIN
                profile.save(update_fields=['role'])

        self.stdout.write(self.style.SUCCESS(f'Synced {count} user profile(s). Platform admins: {UserProfile.objects.filter(role=Role.SUPER_ADMIN).count()}'))
