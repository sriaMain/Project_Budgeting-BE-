# accounts/serializers.py
from rest_framework import serializers
from accounts.models import Account
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
import random
import re
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from .models import PasswordResetOTP
from .tasks import send_otp_email

# class LoginSerializer(serializers.Serializer):
#     # Client should send "identifier" (username or email) and "password".
#     # We also tolerate the client sending "username" or "gmail" for compatibility.
#     identifier = serializers.CharField()           # preferred field (required)
#     # username left here as optional for backward compatibility (not required)
#     username = serializers.CharField(required=False)
#     password = serializers.CharField(write_only=True)

#     def validate(self, attrs):
#         # Accept identifier from (in order):
#         # 1) attrs['identifier'] (preferred)
#         # 2) attrs['username'] (if client used that)
#         # 3) raw input 'gmail' or 'email' (some clients may send these)
#         raw_identifier = (
#             attrs.get("identifier") or
#             attrs.get("username") or
#             self.initial_data.get("gmail") or
#             self.initial_data.get("email")
#         )
#         if raw_identifier is None:
#             raw_identifier = ""
#         identifier = raw_identifier.strip()

#         password = attrs.get("password") or ""

#         # Validate identifier presence
#         if not identifier:
#             raise serializers.ValidationError({"detail": "enter valid username/email"})

#         # Password length check
#         if len(password) < 6:
#             raise serializers.ValidationError({"detail": "enter the valid password of minimium 6 characters"})

#         # Try lookup by username on custom Account, then gmail/email.
#         user = None
#         account_user = None
#         try:
#             account_user = Account.objects.get(username__iexact=identifier)
#         except Account.DoesNotExist:
#             try:
#                 account_user = Account.objects.get(gmail__iexact=identifier)
#             except Account.DoesNotExist:
#                 account_user = None

#         # If we didn't find a matching Account, try Django's built-in User
#         django_user = None
#         if account_user is None:
#             try:
#                 django_user = User.objects.get(username__iexact=identifier)
#             except User.DoesNotExist:
#                 try:
#                     django_user = User.objects.get(email__iexact=identifier)
#                 except User.DoesNotExist:
#                     django_user = None

#         # If neither model matched, return identifier error
#         if account_user is None and django_user is None:
#             raise serializers.ValidationError({"identifier": ["enter valid username/email"]})

#         # Verify password depending on which user we found
#         if account_user is not None:
#             if not check_password(password, account_user.password):
#                 raise serializers.ValidationError({"password": ["enter the valid password"]})
#             user = account_user
#             user_info = {
#                 "id": user.id,
#                 "username": user.username,
#                 "gmail": user.gmail,
#             }
#         else:
#             # django_user is not None here
#             if not django_user.check_password(password):
#                 raise serializers.ValidationError({"password": ["enter the valid password"]})
#             user = django_user
#             user_info = {
#                 "id": user.id,
#                 "username": user.username,
#                 "gmail": getattr(user, "email", ""),
#             }

#         # Create JWT tokens; keep manual user_id claim for compatibility
#         refresh = RefreshToken()
#         access = refresh.access_token
#         access['user_id'] = user.id

#         return {
#             "refresh": str(refresh),
#             "access": str(access),
#             "user": user_info,
#         }

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()   # username / email / gmail
    username = serializers.CharField(required=False)  # backward compatibility
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # Extract identifier (username/email/gmail)
        raw_identifier = (
            attrs.get("identifier") or
            attrs.get("username") or
            self.initial_data.get("gmail") or
            self.initial_data.get("email")
        )

        if raw_identifier is None:
            raw_identifier = ""

        identifier = raw_identifier.strip()
        password = attrs.get("password") or ""

        # -------- IDENTIFIER VALIDATION --------
        if not identifier:
            raise serializers.ValidationError({"error": "Enter valid username/email"})  

        # -------- PASSWORD VALIDATION --------
        if len(password) < 6:
            raise serializers.ValidationError({"error": "Enter the valid password of minimum 6 characters"})

        # -------- LOOKUP USER IN Custom Account Model --------
        account_user = None
        try:
            account_user = Account.objects.get(username__iexact=identifier)
        except Account.DoesNotExist:
            try:
                account_user = Account.objects.get(gmail__iexact=identifier)
            except Account.DoesNotExist:
                account_user = None

        # -------- LOOKUP USER IN Django User Model --------
        django_user = None
        if account_user is None:
            try:
                django_user = User.objects.get(username__iexact=identifier)
            except User.DoesNotExist:
                try:
                    django_user = User.objects.get(email__iexact=identifier)
                except User.DoesNotExist:
                    django_user = None

        # -------- IF NO USER FOUND --------
        if account_user is None and django_user is None:
            raise serializers.ValidationError({"error": "Enter valid username/email"})

        # -------- PASSWORD CHECK --------
        if account_user is not None:
            # Account model user
            if not check_password(password, account_user.password):
                raise serializers.ValidationError({"error": "Enter the valid password"})
            user = account_user
            user_info = {
                "id": user.id,
                "username": user.username,
                "gmail": user.gmail,
            }
        else:
            # Django user
            if not django_user.check_password(password):
                raise serializers.ValidationError({"error": "Enter the valid password"})
            user = django_user
            user_info = {
                "id": user.id,
                "username": user.username,
                "gmail": getattr(user, "email", ""),
            }

        # -------- GENERATE TOKENS --------
        refresh = RefreshToken()
        access = refresh.access_token
        access["user_id"] = user.id

        return {
            "refresh": str(refresh),
            "access": str(access),
            "user": user_info,
        }





class OTPRequestSerializer(serializers.Serializer):
    gmail = serializers.EmailField()

    def validate_email(self, value):
        # ensure email exists either in Account or Django User
        exists = Account.objects.filter(gmail__iexact=value).exists() or User.objects.filter(email__iexact=value).exists()
        if not exists:
            raise serializers.ValidationError({"error":"enter a valid email"})
        return value

    def save(self, **kwargs):
        gmail = self.validated_data['gmail']
        code = f"{random.randint(0, 9999):04d}"
        otp = PasswordResetOTP.objects.create(gmail=gmail, code=code)
        # Enqueue email send via celery
        send_otp_email.delay(gmail, code)
        return otp


class OTPVerifySerializer(serializers.Serializer):
    gmail = serializers.EmailField()
    otp = serializers.CharField()

    def validate(self, attrs):
        gmail = attrs.get('gmail')
        otp = attrs.get('otp', '').strip()
        try:
            otp_rec = PasswordResetOTP.objects.filter(gmail__iexact=gmail, code=otp, is_used=False).latest('created_at')
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError({"otp": "invalid or expired otp"})
        if otp_rec.expired(minutes=getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)):
            raise serializers.ValidationError({"otp": "invalid or expired otp"})
        # Not marking used here — verification only
        attrs['otp_rec'] = otp_rec
        return attrs


# class ResetPasswordSerializer(serializers.Serializer):
#     gmail = serializers.EmailField()
#     otp = serializers.CharField()
#     new_password = serializers.CharField(write_only=True)
#     confirm_password = serializers.CharField(write_only=True)

#     def validate(self, attrs):
#         gmail = attrs.get('gmail')
#         otp = attrs.get('otp', '').strip()
#         new_password = attrs.get('new_password', '')
#         confirm_password = attrs.get('confirm_password', '')

#         # check OTP record
#         try:
#             otp_rec = PasswordResetOTP.objects.filter(gmail__iexact=gmail, code=otp, is_used=False).latest('created_at')
#         except PasswordResetOTP.DoesNotExist:
#             raise serializers.ValidationError({"otp": "invalid or expired otp"})
#         if otp_rec.expired(minutes=getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)):
#             raise serializers.ValidationError({"otp": "expired otp"})

#         # passwords match
#         if new_password != confirm_password:
#             raise serializers.ValidationError({"error": "new_password and confirm_password do not match"})

#         # password policy checks (1) 8 chars, (2) one uppercase, (3) one numeric, (4) one special char
#         errors = []
#         if len(new_password) < 8:
#             errors.append("password must be at least 8 characters")
#         if not re.search(r'[A-Z]', new_password):
#             errors.append("password must contain at least one uppercase letter")
#         if not re.search(r'\d', new_password):
#             errors.append("password must contain at least one numeric digit")
#         if not re.search(r'[^A-Za-z0-9]', new_password):
#             errors.append("password must contain at least one special character")
#         if errors:
#             raise serializers.ValidationError({"error": errors})

#         # attrs['otp_rec'] = otp_rec
#         attrs['new_password_valid'] = new_password
#         return attrs

#     def save(self, **kwargs):
#         gmail = self.validated_data['gmail']
#         new_password = self.validated_data['new_password_valid']
#         otp_rec = self.validated_data['otp_rec']

#         # update Account if present, else update Django User
#         updated = False
#         acc_qs = Account.objects.filter(gmail__iexact=gmail)
#         if acc_qs.exists():
#             acc = acc_qs.first()
#             acc.password = make_password(new_password)
#             acc.save(update_fields=['password'])
#             updated = True
#         else:
#             usr_qs = User.objects.filter(gmail__iexact=gmail)
#             if usr_qs.exists():
#                 u = usr_qs.first()
#                 u.set_password(new_password)
#                 u.save(update_fields=['password'])
#                 updated = True

#         # mark OTP used
#         otp_rec.mark_used()
#         return updated

class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        new_password = attrs.get('new_password', '')
        confirm_password = attrs.get('confirm_password', '')

        if new_password != confirm_password:
            raise serializers.ValidationError({"detail": "new_password and confirm_password do not match"})

        # password policy checks
        errors = []
        if len(new_password) < 8:
            errors.append("password must be at least 8 characters")
        if not re.search(r'[A-Z]', new_password):
            errors.append("password must contain at least one uppercase letter")
        if not re.search(r'\d', new_password):
            errors.append("password must contain at least one numeric digit")
        if not re.search(r'[^A-Za-z0-9]', new_password):
            errors.append("password must contain at least one special character")
        if errors:
            raise serializers.ValidationError({"password": errors})

        attrs['new_password_valid'] = new_password
        return attrs