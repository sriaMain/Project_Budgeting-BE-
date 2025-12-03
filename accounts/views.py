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
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.db.models import Q, Prefetch
from django.core.cache import cache
# import logging
from .serializers import UserCreateSerializer, UserListSerializer, UserDetailSerializer 
import logging
logger = logging.getLogger(__name__)


def format_validation_errors(errors):
    """
    Formats DRF serializer errors into a more user-friendly structure.
    Returns a dictionary where keys are fields and values are the first error message.
    """
    formatted_errors = {}
    if not isinstance(errors, dict):
        return {"error": str(errors)}

    # Handle non-field errors first
    if 'non_field_errors' in errors and errors['non_field_errors']:
        formatted_errors['error'] = errors['non_field_errors'][0]
        return formatted_errors

    # Handle field-specific errors
    for field, messages in errors.items():
        if isinstance(messages, list) and messages:
            message = messages[0]
            field_name = field.replace('_', ' ')
            
            # Custom formatting for specific, common errors
            if "This field is required." in message:
                formatted_errors[field] = f"{field_name.lower()} is required"
            else:
                formatted_errors[field] = message
            
    return formatted_errors


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
        user_id = refresh.payload.get('user_id')
        user = User.objects.get(id=user_id)

        response = Response({
            "message": "Login success",
            "access_token": access, 
            "is_authenticated": user.is_active,       # 🔥 send access token in JSON
            "user": data["user"]
        })

        # Conditionally set cookie attributes based on environment
        if settings.DEBUG:
            # For local development (HTTP)
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                httponly=True,
                max_age=7 * 24 * 60 * 60,
                path="/"
            )
        else:
            # For production (HTTPS)
            response.set_cookie(
                key="refresh_token",
                value=str(refresh),
                httponly=True,
                secure=True,
                samesite="None",
                max_age=7 * 24 * 60 * 60,
                path="/"
            )

        return response




class LogoutView(APIView):
    def post(self, request):
        logout(request)  # destroys the session
        return Response({"message": "Logged out"})



class RefreshTokenCookieView(APIView):
    # authentication_classes = []
    permission_classes = [AllowAny]

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
            "access_token": new_access,
            "is_authenticated": user.is_active,  # Check if user account is active
            "username": user.username,
            "email":  user.email
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
    

class UserCreateView(APIView):
    """
    API endpoint for creating new users with profile pictures.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):  # FIXED: Added 'd' to 'def'
        serializer = UserCreateSerializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            cache.delete("users_list")  # Invalidate user list cache

            return Response(
                {
                    "message": "User created successfully.",
                    "user_id": user.id,
                    "email": user.email,
                    "profile_picture": user.profile_picture.url if user.profile_picture else None
                },
                status=status.HTTP_201_CREATED,
            )

        except DRFValidationError as e:
            errors = format_validation_errors(e.detail)
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            # More specific error message
            error_message = str(e)
            if "email" in error_message.lower():
                details = f"Email '{request.data.get('email')}' already exists."
            else:
                details = "Duplicate record exists."
            
            return Response(
                {"error": "IntegrityError", "details": details},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as e:
            return Response(
                {"error": "ServerError", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
class UserListView(APIView):
    CACHE_TIMEOUT = 120 
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # if not request.user.has_role_permission(self.permission_code):
            #     return Response({"error": "Permission denied"}, status=403)

            cache_key = "users_list"
            cached = cache.get(cache_key)
            if cached:
                return Response(cached, status=200)

            qs = User.objects.filter().prefetch_related(
                Prefetch("roles")
            )
            
            search = request.query_params.get("search")
            if search:
                qs = qs.filter(
                    Q(first_name__icontains=search)
                    | Q(last_name__icontains=search)
                    | Q(email__icontains=search)
                )

            serializer = UserListSerializer(qs, many=True)

            cache.set(cache_key, serializer.data, timeout=self.CACHE_TIMEOUT)
            # cache.delete("users_list")
            return Response(serializer.data, status=200)

        except Exception as e:
            logger.error(f"UserListView Error: {str(e)}", exc_info=True)
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=500,
            )
class UserDetailVieW(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id):

        # if not request.user.has_role_permission(self.permission_code):
        #     return Response({"error": "Permission denied"}, status=403)

        try:
            user = (
                User.objects.filter(is_active=True)
                .prefetch_related("roles")
                .get(id=id)
            )

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        except Exception as e:
            logger.error(f"UserDetailView Error: {str(e)}", exc_info=True)
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=500,
            )

        serializer = UserDetailSerializer(user)
        # cache.delete("users_list")
        return Response(serializer.data, status=200)
    

    # def put(self, request, id):
    #     # if not request.user.has_role_permission(self.permission_code):
    #     #     return Response({"error": "Permission denied"}, status=403)

    #     try:
    #         user = User.objects.get(id=id)

    #     except User.DoesNotExist:
    #         return Response({"error": "User not found"}, status=404)

    #     serializer = UserDetailSerializer(user, data=request.data, partial=True)

    #     try:
    #         serializer.is_valid(raise_exception=True)
    #         serializer.save()
    #         cache.delete("users_list")  # Invalidate cache

    #         return Response(serializer.data, status=200)

    #     except DRFValidationError as e:
    #         errors = format_validation_errors(e.detail)
    #         return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

    #     except Exception as e:
    #         logger.error(f"UserDetailView PUT Error: {str(e)}", exc_info=True)
    #         return Response(
    #             {"error": "Internal server error", "details": str(e)},
    #             status=500,
    #         )

    def put(self, request, id):
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        serializer = UserDetailSerializer(user, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()

            # 🔥 Update roles manually (IMPORTANT)
            if "roles" in request.data:
                user.roles.set(request.data["roles"])

            cache.delete("users_list")

            return Response(serializer.data, status=200)

        except DRFValidationError as e:
            errors = format_validation_errors(e.detail)
            return Response({"errors": errors}, status=400)

        except Exception as e:
            logger.error(f"UserDetailView PUT Error: {str(e)}", exc_info=True)
            return Response({"error": "Internal server error", "details": str(e)}, status=500)
