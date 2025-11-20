from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from .models import Account, PasswordResetOTP
from .serializers import LoginSerializer,OTPRequestSerializer, OTPVerifySerializer, ResetPasswordSerializer

User = get_user_model()

class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        print("LOGIN PAYLOAD:", request.data)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("LOGIN ERRORS:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


#  OTP request view
class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "otp sent to email"}, status=status.HTTP_200_OK)


# OTP verify view
class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp_rec = serializer.validated_data.get('otp_rec')
        otp_rec.is_verified = True
        otp_rec.save(update_fields=['is_verified'])
        return Response({"detail": "otp valid"}, status=status.HTTP_200_OK)


# Reset password view
# class ResetPasswordView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         serializer = ResetPasswordSerializer(data=request.data)
#         # serializer.is_valid(raise_exception=True)
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         updated = serializer.save()
#         if updated:
#             return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
#         return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        # validate only passwords via serializer
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        new_password = serializer.validated_data['new_password_valid']

        # Lookup OTP: prefer verified OTP if model has is_verified, else fallback to latest unused OTP
        otp_rec = None
        if hasattr(PasswordResetOTP, '_meta') and any(f.name == 'is_verified' for f in PasswordResetOTP._meta.get_fields()):
            otp_rec = PasswordResetOTP.objects.filter(is_verified=True, is_used=False).order_by('-created_at').first()
        else:
            otp_rec = PasswordResetOTP.objects.filter(is_used=False).order_by('-created_at').first()

        if not otp_rec:
            return Response({"detail": "no valid otp found; request and verify otp first"}, status=status.HTTP_400_BAD_REQUEST)

        # Check expiry
        expiry_minutes = getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)
        if otp_rec.expired(minutes=expiry_minutes):
            return Response({"detail": "otp expired; request a new otp"}, status=status.HTTP_400_BAD_REQUEST)

        gmail = getattr(otp_rec, 'gmail', None) or getattr(otp_rec, 'email', None)
        if not gmail:
            return Response({"detail": "internal error: otp has no email"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Update Account if present else Django User
        updated = False
        acc_qs = Account.objects.filter(gmail__iexact=gmail)
        if acc_qs.exists():
            acc = acc_qs.first()
            acc.password = make_password(new_password)
            acc.save(update_fields=['password'])
            updated = True
        else:
            usr_qs = User.objects.filter(email__iexact=gmail)
            if usr_qs.exists():
                u = usr_qs.first()
                u.set_password(new_password)
                u.save(update_fields=['password'])
                updated = True

        # mark OTP used
        try:
            if hasattr(otp_rec, 'mark_used'):
                otp_rec.mark_used()
            else:
                otp_rec.is_used = True
                otp_rec.save(update_fields=['is_used'])
        except Exception:
            # don't fail silently in production; log the exception
            pass

        if updated:
            return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
        return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)