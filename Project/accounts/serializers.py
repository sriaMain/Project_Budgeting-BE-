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
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import get_user_model
from django.core.mail import send_mail, BadHeaderError
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

import random
import re

from .models import Account, PasswordResetOTP

User = get_user_model()


# --------------------
# LOGIN SERIALIZER
# --------------------
class LoginSerializer(serializers.Serializer):
    """
    Accepts an 'identifier' (username or gmail/email) and 'password'.
    Returns JWT tokens and basic user info on success.
    """
    identifier = serializers.CharField()
    username = serializers.CharField(required=False)  # backward compatibility
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        #  Extract identifier (username/email/gmail)
        raw_identifier = (
            attrs.get("identifier") or
            attrs.get("username") or
            self.initial_data.get("gmail") or
            self.initial_data.get("email")
        ) or ""

        identifier = raw_identifier.strip()
        password = attrs.get("password") or ""

       # -------- IDENTIFIER VALIDATION --------
        if not identifier:
            raise serializers.ValidationError({"error": "Enter valid username/email"})
       # -------- PASSWORD VALIDATION --------
        if len(password) < 8:
            raise serializers.ValidationError({"error": "Enter the valid password of minimum 8 characters"})

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
            if not check_password(password, account_user.password):
                raise serializers.ValidationError({"error": "Enter the valid password"})
            user = account_user
            user_info = {"id": user.id, "username": user.username, "gmail": user.gmail}
        else:
            if not django_user.check_password(password):
                raise serializers.ValidationError({"error": "Enter the valid password"})
            user = django_user
            user_info = {"id": user.id, "username": user.username, "gmail": getattr(user, "email", "")}

        # -------- GENERATE TOKENS --------
        refresh = RefreshToken()
        access = refresh.access_token
        access["user_id"] = user.id

        return {"refresh": str(refresh), "access": str(access), "user": user_info}


# --------------------
# OTP REQUEST SERIALIZER
# --------------------
class OTPRequestSerializer(serializers.Serializer):
    """
    Request an OTP to be sent to the provided gmail.
    Uses synchronous Django send_mail (SMTP). Validate that the gmail exists
    in either the custom Account model or Django's User model.
    """
    gmail = serializers.EmailField()

    def validate_gmail(self, value):
        # Check if this email exists either in Account or User
        exists_in_account = Account.objects.filter(gmail__iexact=value).exists()
        exists_in_user = User.objects.filter(email__iexact=value).exists()
        if not (exists_in_account or exists_in_user):
            # ValidationError expects a string (or list), not a dict
            raise serializers.ValidationError("Enter a registered email")
        return value

    def save(self, **kwargs):
        gmail = self.validated_data["gmail"]
        # generate 4-digit OTP
        code = f"{random.randint(0, 9999):04d}"
        otp = PasswordResetOTP.objects.create(gmail=gmail, code=code)

        # Build email content
        subject = getattr(settings, "PASSWORD_RESET_SUBJECT", "Your OTP Code")
        message = f"Your password reset OTP is: {code}\nThis OTP is valid for {getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)} minutes."
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        try:
            # synchronous SMTP send
            send_mail(subject, message, from_email, [gmail], fail_silently=False)
        except BadHeaderError:
            # Re-raise as serializer error so view returns 400
            raise serializers.ValidationError({"error":"Invalid header found when sending email"})
        except Exception:
            # Log or return a friendly error
            # In production log the exception; here we raise SerializerError for the client
            raise serializers.ValidationError({"error":"Failed to send OTP email:" })
        return otp


# --------------------
# OTP VERIFY SERIALIZER
# --------------------
class OTPVerifySerializer(serializers.Serializer):
    """
    Verifies the OTP supplied by the user. Attaches the OTP record (otp_record)
    to validated_data so the view can mark it verified and return the reset token.
    """
    gmail = serializers.EmailField()
    otp = serializers.CharField()

    def validate(self, attrs):
        gmail = attrs.get("gmail")
        otp = attrs.get("otp", "").strip()

        otp_queryset = PasswordResetOTP.objects.filter(gmail__iexact=gmail, code=otp, is_used=False)

        # if model has is_verified, ensure we only consider not-yet-verified records
        if hasattr(PasswordResetOTP, "_meta") and any(f.name == "is_verified" for f in PasswordResetOTP._meta.get_fields()):
            otp_queryset = otp_queryset.filter(is_verified=False)

        try:
            otp_record = otp_queryset.latest("created_at")
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError({"error": "invalid or expired otp"})

        # expiration check
        if otp_record.expired(minutes=getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 10)):
            raise serializers.ValidationError({"error": "invalid or expired otp"})

        attrs["otp_rec"] = otp_record
        return attrs


# ---------------------
# RESET PASSWORD SERIALIZER
# ---------------------
class ResetPasswordSerializer(serializers.Serializer):
    """
    Accepts only:
      - new_password
      - confirm_password
    The reset token (UUID) must be provided via header X-Reset-Token OR in the body as 'reset_token'.
    The serializer validates password policy and uses .save(request=context) to perform the reset.
    """
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        new_password = attrs.get("new_password", "")
        confirm_password = attrs.get("confirm_password", "")

        if new_password != confirm_password:
            raise serializers.ValidationError({"error": "new_password and confirm_password do not match"})

        # Single IF for password strength
        if (
            len(new_password) < 8
            or not re.search(r"[A-Z]", new_password)
            or not re.search(r"\d", new_password)
            or not re.search(r"[^A-Za-z0-9]", new_password)
        ):
            raise serializers.ValidationError(
                {"error": ["Password must be 8+ chars, contain an uppercase letter, a number and a special character."]}
            )

        attrs["new_password_valid"] = new_password
        return attrs

    def save(self, **kwargs):
        # We expect the view to pass the request in context so we can read headers
        request = self.context.get("request")
        token = None
        if request:
            token = request.META.get("HTTP_X_RESET_TOKEN")
        token = token or self.initial_data.get("reset_token")

        if not token:
            raise serializers.ValidationError({"error": "reset token required (X-Reset-Token header or reset_token in body)"})

        # find OTP by token
        try:
            otp_record = PasswordResetOTP.objects.get(token=token, is_used=False)
        except PasswordResetOTP.DoesNotExist:
            raise serializers.ValidationError({"error": "invalid or used reset token"})

        # optional: require verification if model supports it
        if hasattr(otp_record, "is_verified") and not getattr(otp_record, "is_verified", False):
            raise serializers.ValidationError({"error": "otp not verified; verify otp first"})

        # OTP-expiry
        if otp_record.expired(minutes=getattr(settings, "PASSWORD_RESET_OTP_EXPIRY_MINUTES", 10)):
            raise serializers.ValidationError({"error": "reset token expired; request a new otp"})

        new_password = self.validated_data["new_password_valid"]
        gmail = getattr(otp_record, "gmail", None) or getattr(otp_record, "email", None)
        if not gmail:
            raise serializers.ValidationError({"error": "internal error: otp has no email"})

        # Update Account (custom) or fallback to Django User\
        updated = False
        account_queryset = Account.objects.filter(gmail__iexact=gmail)
        if account_queryset.exists():
            account = account_queryset.first()
            account.password = make_password(new_password)
            account.save(update_fields=["password"])
            updated = True
        else:
            usr_qs = User.objects.filter(email__iexact=gmail)
            if usr_qs.exists():
                u = usr_qs.first()
                u.set_password(new_password)
                u.save(update_fields=["password"])
                updated = True

        # mark OTP used
        try:
            if hasattr(otp_record, "mark_used"):
                otp_record.mark_used()
            else:
                otp_record.is_used = True
                otp_record.save(update_fields=["is_used"])
        except Exception:
            # In production log the exception. For now we continue.
            pass

        return updated

class ResendOTPSerializer(serializers.Serializer):
    gmail = serializers.EmailField()

    def validate_gmail(self, value):
        # Re-check email exists (for security)
        exists_in_account = Account.objects.filter(gmail__iexact=value).exists()
        exists_in_user = User.objects.filter(email__iexact=value).exists()

        if not (exists_in_account or exists_in_user):
            raise serializers.ValidationError("Enter a registered email")
        return value

    def save(self, **kwargs):
        gmail = self.validated_data['gmail']
        rate_limit_seconds = getattr(settings, "OTP_RATE_LIMIT_SECONDS", 60)
        cache_key = f"otp_rate_{gmail.lower()}"
        if cache.get(cache_key):
            raise serializers.ValidationError({"error": f"Please wait {rate_limit_seconds} seconds before requesting a new OTP."})

        # mark old otps used
        PasswordResetOTP.objects.filter(gmail__iexact=gmail, is_used=False).update(is_used=True)

        code = f"{random.randint(0, 9999):04d}"
        otp = PasswordResetOTP.objects.create(gmail=gmail, code=code)

        # Build email content
        subject = getattr(settings, "PASSWORD_RESET_SUBJECT", "Your OTP Code")
        message = f"Your password reset OTP is: {code}\nThis OTP is valid for {getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)} minutes."
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)

        # send_mail as above...
        try:
            send_mail(subject, message, from_email, [gmail], fail_silently=False)
        except Exception:
            raise serializers.ValidationError({"error": "Failed to send OTP. Please try again later."})

        cache.set(cache_key, True, timeout=rate_limit_seconds)
        return otp

































# from rest_framework import serializers
# from accounts.models import Account
# from django.contrib.auth.hashers import check_password
# from django.contrib.auth.models import User
# from rest_framework_simplejwt.tokens import RefreshToken
# import random
# import re
# from django.conf import settings
# from django.contrib.auth.hashers import make_password
# from django.contrib.auth.models import User
# from .models import PasswordResetOTP
# from .models import Account
# from django.contrib.auth import get_user_model



# class LoginSerializer(serializers.Serializer):
#     identifier = serializers.CharField()   # username / email / gmail
#     username = serializers.CharField(required=False)  # backward compatibility
#     password = serializers.CharField(write_only=True)

#     def validate(self, attrs):
#         # Extract identifier (username/email/gmail)
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

#         # -------- IDENTIFIER VALIDATION --------
#         if not identifier:
#             raise serializers.ValidationError({"error": "Enter valid username/email"})  

#         # -------- PASSWORD VALIDATION --------
#         if len(password) < 6:
#             raise serializers.ValidationError({"error": "Enter the valid password of minimum 6 characters"})

#         # -------- LOOKUP USER IN Custom Account Model --------
#         account_user = None
#         try:
#             account_user = Account.objects.get(username__iexact=identifier)
#         except Account.DoesNotExist:
#             try:
#                 account_user = Account.objects.get(gmail__iexact=identifier)
#             except Account.DoesNotExist:
#                 account_user = None

#         # -------- LOOKUP USER IN Django User Model --------
#         django_user = None
#         if account_user is None:
#             try:
#                 django_user = User.objects.get(username__iexact=identifier)
#             except User.DoesNotExist:
#                 try:
#                     django_user = User.objects.get(email__iexact=identifier)
#                 except User.DoesNotExist:
#                     django_user = None

#         # -------- IF NO USER FOUND --------
#         if account_user is None and django_user is None:
#             raise serializers.ValidationError({"error": "Enter valid username/email"})

#         # -------- PASSWORD CHECK --------
#         if account_user is not None:
#             # Account model user
#             if not check_password(password, account_user.password):
#                 raise serializers.ValidationError({"error": "Enter the valid password"})
#             user = account_user
#             user_info = {
#                 "id": user.id,
#                 "username": user.username,
#                 "gmail": user.gmail,
#             }
#         else:
#             # Django user
#             if not django_user.check_password(password):
#                 raise serializers.ValidationError({"error": "Enter the valid password"})
#             user = django_user
#             user_info = {
#                 "id": user.id,
#                 "username": user.username,
#                 "gmail": getattr(user, "email", ""),
#             }

#         # -------- GENERATE TOKENS --------
#         refresh = RefreshToken()
#         access = refresh.access_token
#         access["user_id"] = user.id

#         return {
#             "refresh": str(refresh),
#             "access": str(access),
#             "user": user_info,
#         }





# User = get_user_model()

# class OTPRequestSerializer(serializers.Serializer):
#     gmail = serializers.EmailField()

#     def validate_gmail(self, value):
#         # Check if this email exists either in Account or User
#         exists_in_account = Account.objects.filter(gmail__iexact=value).exists()
#         exists_in_user = User.objects.filter(email__iexact=value).exists()

#         if not (exists_in_account or exists_in_user):
#             # this will attach error to the 'gmail' field
#             raise serializers.ValidationError({"error":"Enter a registered email"})

#         return value


#     def save(self, **kwargs):
#         gmail = self.validated_data['gmail']
#         code = f"{random.randint(0, 9999):04d}"
#         otp = PasswordResetOTP.objects.create(gmail=gmail, code=code)
        
#         return otp


# class OTPVerifySerializer(serializers.Serializer):
#     gmail = serializers.EmailField()
#     otp = serializers.CharField()

#     def validate(self, attrs):
#         gmail = attrs.get('gmail')
#         otp = attrs.get('otp', '').strip()
#          # Base queryset: not used
#         qs = PasswordResetOTP.objects.filter(
#             gmail__iexact=gmail,
#             code=otp,
#             is_used=False
#         )

#         # If model has is_verified, exclude already-verified OTPs
#         if hasattr(PasswordResetOTP, "_meta") and any(
#             f.name == "is_verified" for f in PasswordResetOTP._meta.get_fields()
#         ):
#             qs = qs.filter(is_verified=False)

#         try:
#             otp_rec = qs.latest('created_at')
#         except PasswordResetOTP.DoesNotExist:
#             raise serializers.ValidationError({"otp": "invalid or expired otp"})

#         # Expiry check
#         if otp_rec.expired(
#             minutes=getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)
#         ):
#             raise serializers.ValidationError({"otp": "invalid or expired otp"})

#         attrs['otp_rec'] = otp_rec
#         return attrs
        
    
# class ResetPasswordSerializer(serializers.Serializer):
#     new_password = serializers.CharField(write_only=True)
#     confirm_password = serializers.CharField(write_only=True)

#     def validate(self, attrs):
#         new_password = attrs.get('new_password', '')
#         confirm_password = attrs.get('confirm_password', '')

#         if new_password != confirm_password:
#             raise serializers.ValidationError({"detail": "new_password and confirm_password do not match"})

#         errors = []
#         if (
#         len(new_password) < 8 or
#         not re.search(r'[A-Z]', new_password) or
#         not re.search(r'\d', new_password) or
#         not re.search(r'[^A-Za-z0-9]', new_password)
#         ):
            
#             raise serializers.ValidationError({
#         "error": [
#              "Password does not meet the required strength."
#         ]
#     })


#         # store validated password for .save()
#         attrs['new_password_valid'] = new_password
#         return attrs

#     def save(self, **kwargs):
#         """
#         Expect the view to pass request in context so we can read header/body reset_token.
#         """
#         request = self.context.get('request')
#         token = None
#         if request:
#             token = request.META.get('HTTP_X_RESET_TOKEN')  # header: X-Reset-Token
#         token = token or self.initial_data.get('reset_token')

#         if not token:
#             raise serializers.ValidationError({"detail": "reset token required (X-Reset-Token header or reset_token in body)"})

#         # lookup OTP by token
#         try:
#             otp_rec = PasswordResetOTP.objects.get(token=token, is_used=False)
#         except PasswordResetOTP.DoesNotExist:
#             raise serializers.ValidationError({"detail": "invalid or used reset token"})

#         # optional: require otp_rec.is_verified if your model has it
#         if hasattr(otp_rec, 'is_verified') and not getattr(otp_rec, 'is_verified', False):
#             raise serializers.ValidationError({"detail": "otp not verified; verify otp first"})

#         # check expiry
#         if otp_rec.expired(minutes=getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)):
#             raise serializers.ValidationError({"detail": "reset token expired; request a new otp"})

#         new_password = self.validated_data['new_password_valid']
#         gmail = getattr(otp_rec, 'gmail', None) or getattr(otp_rec, 'email', None)
#         if not gmail:
#             raise serializers.ValidationError({"detail": "internal error: otp has no email"})

#         # update Account if present, else update Django User
#         updated = False
#         acc_qs = Account.objects.filter(gmail__iexact=gmail)
#         if acc_qs.exists():
#             acc = acc_qs.first()
#             acc.password = make_password(new_password)
#             acc.save(update_fields=['password'])
#             updated = True
#         else:
#             usr_qs = User.objects.filter(email__iexact=gmail)
#             if usr_qs.exists():
#                 u = usr_qs.first()
#                 u.set_password(new_password)
#                 u.save(update_fields=['password'])
#                 updated = True

#         # mark OTP used
#         otp_rec.mark_used()

#         return updated


