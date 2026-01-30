
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
from django.db.models import Q
from rest_framework.validators import UniqueValidator
from roles.models import Role
from product_group.models import Product_Services
import uuid

User = get_user_model()

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier").strip()
        password = attrs.get("password")

        # ✅ Find user by email OR username OR full name
        user = Account.objects.filter(
            Q(email__iexact=identifier) |
            Q(username__iexact=identifier) |
            Q(first_name__iexact=identifier) |
            Q(last_name__iexact=identifier) |
            Q(first_name__iexact=identifier.split(" ")[0]) |
            Q(first_name__iexact=identifier) |
            Q(first_name__iexact=identifier)  # safe fallback
        ).first()

        if not user:
            raise serializers.ValidationError({"error": "User not found."})

        if not user.is_active:
            raise serializers.ValidationError({"error": "Your account is inactive. Please contact admin."})

        # ✅ authenticate always needs username internally
        auth_user = authenticate(username=user.username, password=password)

        if not auth_user:
            raise serializers.ValidationError({"error": "Invalid password."})

        refresh = RefreshToken.for_user(auth_user)

        return {
            "access": str(refresh.access_token),
            "refresh": refresh,
            "user": {
                "id": auth_user.id,
                "email": auth_user.email,
                "username": auth_user.username,
                "first_name": auth_user.first_name,
                "last_name": auth_user.last_name,
            }
        }

class OTPRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs.get("email", "").strip()
        if not email:
            raise serializers.ValidationError({"error": "Invalid email"})
        
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise serializers.ValidationError({"error": "Email not registered"})
        
        self._user = user
        attrs["email"] = email
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
        send_mail(subject, msg, from_email, [self.validated_data["email"]], fail_silently=False)
        ist = pytz.timezone('Asia/Kolkata')
        otp_sent_at_ist = otp_obj.created_at.astimezone(ist)
        
        return {
            "sent": True,
            "otp_sent_at": otp_sent_at_ist.isoformat()
        }

class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()

    def validate(self, attrs):
        email = attrs.get("email")
        raw = attrs.get("otp", "").strip()
        if not raw.isdigit() or len(raw) != 4:
            raise serializers.ValidationError({"error": "Invalid OTP format"})

        user = User.objects.filter(email__iexact=email).first()
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


class UserListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "position",
            "module",
            "charges_per_hour",
            "roles",
            'profile_picture',
            "is_active",
            "languages"
        ]

    def get_roles(self, obj):
        return [r.id for r in obj.roles.all()]
        


class UserDetailSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "position",
            "module",
            "charges_per_hour",
            "profile_picture",
            "roles",
            "languages",
            "created_at",
            "modified_at",
            "is_active",
        ]

    def get_roles(self, obj):
        return [r.id for r in obj.roles.all()]
    


class UserCreateSerializer(serializers.ModelSerializer):
    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),   # allow lookup
        many=True,
        required=True,
        allow_empty=False,
        error_messages={
            'required': 'The roles field is required.',
            'allow_empty': 'At least one role must be selected.',
        }
    )

    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=Account.objects.all(),
                message="A user with this email already exists."
            )
        ]
    )

    first_name = serializers.CharField(required=True)
    position = serializers.CharField(required=True)

    module = serializers.PrimaryKeyRelatedField(
        queryset=Product_Services.objects.all(),
        required=True
    )

    charges_per_hour = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=True
    )
    currency = serializers.ChoiceField(
        choices=[("INR", "INR"), ("USD", "USD"), ("EUR", "EUR")],
        required=False,
        default="INR"
    )

    class Meta:
        model = Account
        fields = [
            "first_name",
            "last_name",
            "email",
            "position",
            "module",
            "charges_per_hour",
            "currency", 
            "roles",
            "profile_picture",
            "languages",
            "is_active",
        ]

    # 🔒 BLOCK INACTIVE ROLES
    def validate_roles(self, roles):
        inactive_roles = [r.role_name for r in roles if not r.is_active]

        if inactive_roles:
            raise serializers.ValidationError(
                f"Inactive roles cannot be assigned: {', '.join(inactive_roles)}."
            )

        return roles

    def validate_charges_per_hour(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Charges per hour must be positive."
            )
        return value

    def create(self, validated_data):
        import uuid, random, string

        roles = validated_data.pop("roles")
        email = validated_data.pop("email").lower().strip()

        username = f"{email.split('@')[0]}-{uuid.uuid4().hex[:8]}"
        password = ''.join(
            random.choices(string.ascii_letters + string.digits, k=10)
        )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            **validated_data
        )

        user.roles.set(roles)

        user.is_staff = any(
            role.role_name == "Admin" for role in roles
        )
        user.save(update_fields=["is_staff"])

        send_mail(
            subject="Your Account Registration",
            message=(
                f"Hello {user.get_full_name() or user.username},\n\n"
                f"Your account has been created.\n"
                f"Password: {password}\n\n"
                f"Please change your password after logging in."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        return user

from rest_framework import serializers
from .models import Vendor

class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = '__all__'









