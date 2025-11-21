from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
from django.contrib.auth.models import AbstractUser as AbstactUser

#creating the models
class Account(AbstactUser):
    username = models.CharField(max_length=150, unique=True)
    gmail = models.EmailField(unique=True)
    password = models.CharField(max_length=255)  # hashed
    def __str__(self):
        return self.username

class PasswordResetOTP(models.Model):
    """
    Stores OTP codes sent to emails for password reset.
    """
    gmail = models.EmailField(db_index=True)
    code = models.CharField(max_length=10)  # store e.g. "1234"
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    # optional: a UUID token (not necessary for our flow but handy)
    token = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=['gmail', 'code']),
        ]

    def expired(self, minutes=10):
        return timezone.now() > self.created_at + timedelta(minutes=minutes)

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])