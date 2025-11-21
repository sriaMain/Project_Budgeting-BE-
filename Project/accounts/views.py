# accounts/views.py
"""
Views for account auth and password-reset flow.

Flow:
- POST /api/accounts/login/          -> LoginView (identifier + password) -> JWTs
- POST /api/accounts/otp-request/    -> OTPRequestView (gmail) -> sends OTP via SMTP
- POST /api/accounts/verify-otp/     -> OTPVerifyView (gmail + otp) -> returns reset_token
- POST /api/accounts/reset-password/ -> ResetPasswordView (new_password + confirm_password, header X-Reset-Token)
"""

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import serializers
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model

from .models import Account, PasswordResetOTP
from .serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    ResetPasswordSerializer,ResendOTPSerializer
)


User = get_user_model()


# --------------------
# LOGIN VIEW
# --------------------
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Keep logs for debugging; remove or replace with proper logger in production.
        print("LOGIN PAYLOAD:", request.data)
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            print("LOGIN ERRORS:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# --------------------
# OTP REQUEST VIEW
# --------------------
class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Validates the gmail and synchronously sends an OTP email using SMTP.
        Returns 200 on success or 400 with the validation/send error.
        """
        serializer = OTPRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            serializer.save()
        except serializers.ValidationError as ve:
            # serializer.save() can raise ValidationError if sending email fails
            return Response({"error": ve.detail if hasattr(ve, "detail") else str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            # Unexpected error
            return Response({"error": f"failed to send otp: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "OTP sent to email"}, status=status.HTTP_200_OK)


# --------------------
# OTP VERIFY VIEW
# --------------------
class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Verifies the OTP. On success marks OTP as verified (if the model supports it),
        and returns a reset_token (UUID) for the next step.
        """
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp_rec = serializer.validated_data.get("otp_rec")

        # Mark verified if the model supports the field
        try:
            if hasattr(otp_rec, "is_verified"):
                otp_rec.is_verified = True
                otp_rec.save(update_fields=["is_verified"])
        except Exception as exc:
            # Log in production; return friendly error to client
            return Response({"error": f"failed to mark otp verified: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Return reset token so client can call reset-password
        return Response({"detail": "otp valid", "reset_token": str(otp_rec.token)}, status=status.HTTP_200_OK)


# --------------------
# RESET PASSWORD VIEW
# --------------------
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        """
        Accepts only new_password + confirm_password in body.
        Client MUST provide reset token (header X-Reset-Token OR body reset_token).
        """
        serializer = ResetPasswordSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            updated = serializer.save()
        except serializers.ValidationError as ve:
            return Response({"error": ve.detail if hasattr(ve, "detail") else str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"error": f"internal error while resetting password: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if updated:
            return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
        return Response({"error": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ResendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            serializer.save()
        except serializers.ValidationError as ve:
            return Response({"error": ve.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "OTP resent successfully"}, status=status.HTTP_200_OK)



























# from rest_framework import generics, permissions, status
# from rest_framework.views import APIView
# from rest_framework.permissions import AllowAny
# from rest_framework.response import Response
# from django.conf import settings
# from django.contrib.auth import get_user_model
# from django.contrib.auth.hashers import make_password
# from .models import Account, PasswordResetOTP
# from .serializers import LoginSerializer,OTPRequestSerializer, OTPVerifySerializer, ResetPasswordSerializer

# User = get_user_model()

# class LoginView(generics.GenericAPIView):
#     serializer_class = LoginSerializer
#     permission_classes = [permissions.AllowAny]

#     def post(self, request):
#         print("LOGIN PAYLOAD:", request.data)
#         serializer = self.get_serializer(data=request.data)
#         if not serializer.is_valid():
#             print("LOGIN ERRORS:", serializer.errors)
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         return Response(serializer.validated_data, status=status.HTTP_200_OK)


# #  OTP request view
# class OTPRequestView(APIView):
#     permission_classes = [AllowAny]
#     def post(self, request, *args, **kwargs):
#         serializer = OTPRequestSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response({"message": "otp sent to email"}, status=status.HTTP_200_OK)


# # OTP verify view
# class OTPVerifyView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         serializer = OTPVerifySerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         otp_rec = serializer.validated_data.get('otp_rec')
#         if hasattr(otp_rec, 'is_verified'):
#             otp_rec.is_verified = True
#             otp_rec.save(update_fields=['is_verified'])

#         # Return the existing UUID token to the client (use this for reset)
#         return Response({"detail": "otp valid", "reset_token": str(otp_rec.token)}, status=status.HTTP_200_OK)
    
        

# class ResetPasswordView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         serializer = ResetPasswordSerializer(data=request.data, context={'request': request})
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#         updated = serializer.save()
#         if updated:
#             return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
#         return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)


#         if updated:
#             return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
#         return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)