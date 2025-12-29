from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Role

@receiver(post_save, sender=Role)
@receiver(post_delete, sender=Role)
def clear_roles_cache(sender, **kwargs):
    cache.delete("roles_list_v1")