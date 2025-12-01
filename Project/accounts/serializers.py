# # accounts/serializers.py
"""
Serializers for:
 - Login (username/email + password)
 - OTP request (send OTP via SMTP)
 - OTP verify (check OTP and return reset token)
 - Reset password (accept reset_token + new passwords and update the account)
Notes:
 - This version uses synchronous SMTP (django.core.mail.send_mail).
 - The reset flow returns a reset_token in verify step; the reset endpoint uses that.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import Account, PasswordResetOTP
import pytz

User = get_user_model()

# --------------------
# LOGIN
# --------------------
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        if not identifier:
            raise serializers.ValidationError({"error": "Identifier required"})
        if len(password) < 8:
            raise serializers.ValidationError({"error": "Invalid password (min 8 chars)"})

        # Resolve user (username or gmail or email)
        user = None
        if "@" in identifier:
            # try gmail first then email
            user = Account.objects.filter(gmail__iexact=identifier).first() or \
                   User.objects.filter(email__iexact=identifier).first()
            if not user:
                raise serializers.ValidationError({"error": "Email not registered"})
        else:
            user = Account.objects.filter(username__iexact=identifier).first() or \
                   User.objects.filter(username__iexact=identifier).first()
            if not user:
                raise serializers.ValidationError({"error": "Username not found"})

        if not user.check_password(password):
            raise serializers.ValidationError({"error": "Invalid password"})

        refresh = RefreshToken.for_user(user)
        data = {
            "refresh": refresh,
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "gmail": getattr(user, "gmail", None) or getattr(user, "email", None)
            }
        }
        return data




class OTPRequestSerializer(serializers.Serializer):
    gmail = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        gmail = attrs.get("gmail", "").strip()
        if not gmail:
            raise serializers.ValidationError({"error": "Email required"})
        
        user = Account.objects.filter(gmail__iexact=gmail).first() or \
               User.objects.filter(email__iexact=gmail).first()
        if not user:
            raise serializers.ValidationError({"error": "Email not registered"})
        
        self._user = user
        attrs["gmail"] = gmail
        return attrs

    def save(self, **kwargs):
        # Check if user is in cooldown (10 min block after 3 attempts)
        cooldown_key = f"otp_cooldown_{self._user.id}"
        if cache.get(cooldown_key):
            raise serializers.ValidationError({"error": "Too many attempts. Please wait 10 minutes to resend otp"})
        
        # Check attempt count
        attempt_key = f"otp_attempts_{self._user.id}"
        attempts = cache.get(attempt_key, 0)
        
        if attempts >= 3:
            # Block for 10 minutes
            cache.set(cooldown_key, True, timeout=600)  # 10 minutes
            cache.delete(attempt_key)
            raise serializers.ValidationError({"error": "Too many attempts. Please wait 10 minutes to resend otp"})
        
        # Check basic rate limit (60 seconds between requests)
        rate_key = f"otp_req_{self._user.id}"
        if cache.get(rate_key):
            raise serializers.ValidationError({"error": "Wait one minute before requesting new otp"})
        
        # Increment attempt counter
        cache.set(attempt_key, attempts + 1, timeout=600)  # Track attempts for 10 minutes
        
        # Create and send OTP
        otp_obj, raw_code = PasswordResetOTP.create_for_user(self._user, length=4)
        cache.set(rate_key, True, timeout=60)
        
        subject = getattr(settings, "PASSWORD_RESET_SUBJECT", "Password Reset OTP")
        minutes = getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 2)
        msg = f"Your OTP is {raw_code}. Expires in {minutes} minutes."
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        send_mail(subject, msg, from_email, [self.validated_data["gmail"]], fail_silently=False)
        ist = pytz.timezone('Asia/Kolkata')
        otp_sent_at_ist = otp_obj.created_at.astimezone(ist)
        
        return {
            "sent": True,
            "otp_sent_at": otp_sent_at_ist.isoformat()
        }

# --------------------
# OTP VERIFY
# --------------------
class OTPVerifySerializer(serializers.Serializer):
    gmail = serializers.EmailField()
    otp = serializers.CharField()

    def validate(self, attrs):
        gmail = attrs.get("gmail")
        raw = attrs.get("otp", "").strip()
        if not raw.isdigit() or len(raw) != 4:
            raise serializers.ValidationError({"error": "Invalid OTP format"})

        user = Account.objects.filter(gmail__iexact=gmail).first() or \
               User.objects.filter(email__iexact=gmail).first()
        if not user:
            raise serializers.ValidationError({"error": "Email not registered"})

        # Get the most recent active OTP
        otp_obj = PasswordResetOTP.active_qs_for_user(user).order_by('-created_at').first()
        
        if not otp_obj:
            # No active OTP found - check if they're entering an old/expired code
            # Try to find ANY recent OTP (within last 10 minutes) to give better error
            from datetime import timedelta
            from django.utils import timezone
            recent_cutoff = timezone.now() - timedelta(minutes=10)
            any_recent = PasswordResetOTP.objects.filter(
                user=user, 
                created_at__gt=recent_cutoff
            ).order_by('-created_at').first()
            
            if any_recent:
                # They have a recent OTP but it's either expired or used
                from django.contrib.auth.hashers import check_password
                if check_password(raw, any_recent.code_hash):
                    # They entered the correct code but it's expired/used
                    raise serializers.ValidationError({"error": "OTP has expired"})
                else:
                    # Wrong code
                    raise serializers.ValidationError({"error": "Invalid OTP"})
            else:
                raise serializers.ValidationError({"error": "OTP has expired"})
        
        # Check if expired
        if otp_obj.expired():
            raise serializers.ValidationError({"error": "OTP has expired"})
        
        # Check if already used
        if otp_obj.is_used:
            raise serializers.ValidationError({"error": "OTP already used"})
        
        # Verify the code
        from django.contrib.auth.hashers import check_password
        if not check_password(raw, otp_obj.code_hash):
            raise serializers.ValidationError({"error": "Invalid OTP"})
        
        # Mark as verified
        otp_obj.is_verified = True
        otp_obj.save(update_fields=["is_verified"])
        attrs["reset_token"] = str(otp_obj.token)
        attrs["user_id"] = user.id
        return attrs

# --------------------
# RESET PASSWORD
# --------------------
class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.UUIDField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        np = attrs.get("new_password", "")
        cp = attrs.get("confirm_password", "")
        if np != cp:
            raise serializers.ValidationError({"error": "Passwords do not match"})
        if len(np) < 8:
            raise serializers.ValidationError({"error": "Invalid password (min 8 chars)"})
        attrs["valid_pw"] = np
        return attrs

    def save(self, **kwargs):
        token = self.validated_data["reset_token"]
        try:
            otp_obj = PasswordResetOTP.objects.get(token=token, is_verified=True, is_used=False)
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError({"error": "Invalid or used reset token"})

        if otp_obj.expired():
            raise serializers.ValidationError({"error": "Reset token expired"})

        user = otp_obj.user
        user.password = make_password(self.validated_data["valid_pw"])
        user.save(update_fields=["password"])
        otp_obj.mark_used()
        return {"reset": True}

# --------------------
# RESEND OTP
# --------------------
class ResendOTPSerializer(serializers.Serializer):
    gmail = serializers.EmailField()

    def validate_gmail(self, value):
        user = Account.objects.filter(gmail__iexact=value).first() or \
               User.objects.filter(email__iexact=value).first()
        if not user:
            raise serializers.ValidationError({"error": "Email not registered"})
        self._user = user
        return value

    def save(self, **kwargs):
        # Check cooldown
        cooldown_key = f"otp_cooldown_{self._user.id}"
        if cache.get(cooldown_key):
            raise serializers.ValidationError({"error": "Too many attempts. Please wait 10 minutes to resend otp"})
        
        # Check attempt count
        attempt_key = f"otp_attempts_{self._user.id}"
        attempts = cache.get(attempt_key, 0)
        
        if attempts >= 3:
            cache.set(cooldown_key, True, timeout=600)
            cache.delete(attempt_key)
            raise serializers.ValidationError({"error": "Too many attempts. Please wait 10 minutes to resend otp"})
        
        # Increment attempts
        cache.set(attempt_key, attempts + 1, timeout=600)
        
        # ✅ UNCOMMENT THIS - Invalidate old OTPs so only new one is valid
        PasswordResetOTP.objects.filter(user=self._user, is_used=False).update(is_used=True)
        
        otp_obj, raw_code = PasswordResetOTP.create_for_user(self._user, length=4)
        
        subject = getattr(settings, "PASSWORD_RESET_SUBJECT", "Password Reset OTP")
        minutes = getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 2)
        msg = f"Your OTP is {raw_code}. Expires in {minutes} minutes."
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        send_mail(subject, msg, from_email, [self.validated_data["gmail"]], fail_silently=False)
        
        ist = pytz.timezone('Asia/Kolkata')
        otp_sent_at_ist = otp_obj.created_at.astimezone(ist)
        
        return {
            "resent": True,
            "otp_sent_at": otp_sent_at_ist.isoformat()
        }

































