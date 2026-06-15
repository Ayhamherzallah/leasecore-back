from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile, Role


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = Role.SUPER_ADMIN if instance.is_superuser else Role.BUILDING_MANAGER
        UserProfile.objects.create(user=instance, role=role)
    elif instance.is_superuser:
        profile, _ = UserProfile.objects.get_or_create(
            user=instance,
            defaults={'role': Role.SUPER_ADMIN},
        )
        if profile.role != Role.SUPER_ADMIN:
            profile.role = Role.SUPER_ADMIN
            profile.save(update_fields=['role'])
