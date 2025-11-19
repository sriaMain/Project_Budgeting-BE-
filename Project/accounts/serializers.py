# accounts/serializers.py
from rest_framework import serializers
from accounts.models import Account
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken


class LoginSerializer(serializers.Serializer):
    # Client should send "identifier" (username or email) and "password".
    # We also tolerate the client sending "username" or "gmail" for compatibility.
    identifier = serializers.CharField()           # preferred field (required)
    # username left here as optional for backward compatibility (not required)
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        # Accept identifier from (in order):
        # 1) attrs['identifier'] (preferred)
        # 2) attrs['username'] (if client used that)
        # 3) raw input 'gmail' or 'email' (some clients may send these)
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

        # Validate identifier presence
        if not identifier:
            raise serializers.ValidationError({"detail": "enter valid username/email"})

        # Password length check
        if len(password) < 6:
            raise serializers.ValidationError({"detail": "enter the valid password of minimium 6 characters"})

        # Try lookup by username on custom Account, then gmail/email.
        user = None
        account_user = None
        try:
            account_user = Account.objects.get(username__iexact=identifier)
        except Account.DoesNotExist:
            try:
                account_user = Account.objects.get(gmail__iexact=identifier)
            except Account.DoesNotExist:
                account_user = None

        # If we didn't find a matching Account, try Django's built-in User
        django_user = None
        if account_user is None:
            try:
                django_user = User.objects.get(username__iexact=identifier)
            except User.DoesNotExist:
                try:
                    django_user = User.objects.get(email__iexact=identifier)
                except User.DoesNotExist:
                    django_user = None

        # If neither model matched, return identifier error
        if account_user is None and django_user is None:
            raise serializers.ValidationError({"identifier": ["enter valid username/email"]})

        # Verify password depending on which user we found
        if account_user is not None:
            if not check_password(password, account_user.password):
                raise serializers.ValidationError({"password": ["enter the valid password"]})
            user = account_user
            user_info = {
                "id": user.id,
                "username": user.username,
                "gmail": user.gmail,
            }
        else:
            # django_user is not None here
            if not django_user.check_password(password):
                raise serializers.ValidationError({"password": ["enter the valid password"]})
            user = django_user
            user_info = {
                "id": user.id,
                "username": user.username,
                "gmail": getattr(user, "email", ""),
            }

        # Create JWT tokens; keep manual user_id claim for compatibility
        refresh = RefreshToken()
        access = refresh.access_token
        access['user_id'] = user.id

        return {
            "refresh": str(refresh),
            "access": str(access),
            "user": user_info,
        }

