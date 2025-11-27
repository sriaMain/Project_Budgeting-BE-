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
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Account, PasswordResetOTP
from .serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    ResetPasswordSerializer,
    ResendOTPSerializer
)

User = get_user_model()


# --------------------
# LOGIN VIEW
# --------------------
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------
# OTP REQUEST VIEW
# --------------------
class OTPRequestView(APIView):
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"detail": "OTP sent", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------
# OTP VERIFY VIEW
# --------------------
class OTPVerifyView(APIView):
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            reset_token = serializer.validated_data.get('reset_token')
            return Response({
                "detail": "OTP valid",
                "reset_token": reset_token
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------
# RESET PASSWORD VIEW
# --------------------
class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"detail": "Password reset successful", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------
# RESEND OTP VIEW
# --------------------
class ResendOTPView(APIView):
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"detail": "OTP resent", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)