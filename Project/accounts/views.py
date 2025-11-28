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
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
import jwt
from datetime import datetime, timezone
from django.contrib.auth import logout



from .models import Account, PasswordResetOTP
from .serializers import (
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    ResetPasswordSerializer,
    ResendOTPSerializer
)

User = get_user_model()




class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        access = data["access"]
        refresh = data["refresh"]

        response = Response({
            "message": "Login success",
            "access_token": access,        # 🔥 send access token in JSON
            "user": data["user"]
        })

        # 🔥 send refresh token as secure cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=True,
            secure=False,   # True in production
            samesite="Lax",
            max_age=7 * 24 * 60 * 60,
            path="/"
        )

        return response




class LogoutView(APIView):
    def post(self, request):
        logout(request)  # destroys the session
        return Response({"message": "Logged out"})



class RefreshTokenCookieView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"error": "Refresh token missing"}, status=401)

        try:
            refresh = RefreshToken(refresh_token)
            user_id = refresh.payload.get('user_id')
            user = User.objects.get(id=user_id)
        except (TokenError, User.DoesNotExist, Exception):
            return Response({"error": "Invalid refresh token"}, status=401)

        new_access = str(refresh.access_token)

        return Response({
            "access": new_access,
            "is_authenticated": user.is_active,  # Check if user account is active
            "username": user.username,
            "gmail": user.gmail or user.email
        })



# --------------------
# OTP REQUEST VIEW
# --------------------
class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"message": "OTP sent", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# --------------------
# OTP VERIFY VIEW
# --------------------
class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
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
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"message": "Password reset successful", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LogoutView(APIView):
    def post(self, request):
        response = Response({"message": "Logged out"}, status=200)
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        return response



# --------------------
# RESEND OTP VIEW
# --------------------
class ResendOTPView(APIView):
    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            return Response({"message": "OTP resent", **result}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)