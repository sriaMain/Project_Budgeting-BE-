from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Quote
from .tasks import send_quotation_status_change_email


@receiver(pre_save, sender=Quote)
def detect_quotation_status_change(sender, instance, **kwargs):
    """
    Detect when a quotation's status changes and trigger email notification.
    This signal fires before the model is saved.
    """
    # Only process if this is an update (instance already exists in DB)
    if instance.pk:
        try:
            # Get the old instance from database
            old_instance = Quote.objects.get(pk=instance.pk)
            old_status = old_instance.status
            new_status = instance.status
            
            # Check if status has changed
            if old_status != new_status:
                # Trigger async email task after the save completes
                # We use transaction.on_commit to ensure the task runs after DB commit
                from django.db import transaction
                transaction.on_commit(
                    lambda: send_quotation_status_change_email.delay(
                        instance.pk, 
                        old_status, 
                        new_status
                    )
                )
        except Quote.DoesNotExist:
            # This shouldn't happen, but handle it gracefully
            pass
