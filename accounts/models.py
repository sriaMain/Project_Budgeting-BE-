from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import random
from roles.models import RBACUserMixin# from rbac.models import RBACUserMixin
from cloudinary_storage.storage import MediaCloudinaryStorage


class Account(AbstractUser, RBACUserMixin):
    email = models.EmailField(unique=True, null=True, blank=True, db_index=True)
    position = models.CharField(max_length=100, blank=True)
    module = models.ForeignKey(
        'product_group.Product_Services', on_delete=models.SET_NULL,
        related_name='accounts', null=True, blank=True
    )
    charges_per_hour = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    # Do not force a specific storage backend here — use the project's
    # DEFAULT_FILE_STORAGE. This avoids instantiating Cloudinary storage
    # during model import when Cloudinary credentials may be invalid.
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        null=True,
        blank=True,
        storage=MediaCloudinaryStorage()
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    is_active =models.BooleanField(default=True)
    # languages =models.CharField(max_length=100, blank=True)
    languages = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.get_full_name()} ({self.email or self.username})"


class PasswordResetOTP(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_otps'
    )
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    token = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]

    def expired(self, minutes=2):
        return timezone.now() > self.created_at + timedelta(minutes=minutes)

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used'])

    def set_code(self, raw_code: str):
        self.code_hash = make_password(raw_code)

    def verify_code(self, raw_code: str):
        if self.is_used or self.expired():
            return False
        ok = check_password(raw_code, self.code_hash)
        if ok:
            self.is_verified = True
            self.save(update_fields=['is_verified'])
            # Don't mark as used here - only mark used when password is actually reset
        return ok

    @classmethod
    def active_qs_for_user(cls, user):
        expiry_seconds = getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_SECONDS', 30)
        cutoff = timezone.now() - timedelta(seconds=expiry_seconds)
        return cls.objects.filter(
            user=user,
            is_used=False,
            created_at__gt=cutoff
        )

    @classmethod
    def create_for_user(cls, user, length=6):
        raw = ''.join(str(random.randint(0, 9)) for _ in range(length))
        obj = cls(user=user)
        obj.set_code(raw)
        obj.save()
        return obj, raw