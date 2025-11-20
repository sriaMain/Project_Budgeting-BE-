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
    # permission_classes = [IsAuthenticated]
    # authentication_classes = [JWTAuthentication]

    def post(self, request, *args, **kwargs):

        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "otp sent to email"}, status=status.HTTP_200_OK)


# OTP verify view
class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp_rec = serializer.validated_data.get('otp_rec')
        if hasattr(otp_rec, 'is_verified'):
            otp_rec.is_verified = True
            otp_rec.save(update_fields=['is_verified'])

        # Return the existing UUID token to the client (use this for reset)
        return Response({"detail": "otp valid", "reset_token": str(otp_rec.token)}, status=status.HTTP_200_OK)
    
        # otp_rec.is_verified = True
        # otp_rec.save(update_fields=['is_verified'])
        # return Response({"detail": "otp valid"}, status=status.HTTP_200_OK)


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


# accounts/views.py (ResetPasswordView)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        updated = serializer.save()
        if updated:
            return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
        return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)


        if updated:
            return Response({"detail": "password reset successful"}, status=status.HTTP_200_OK)
        return Response({"detail": "no account updated"}, status=status.HTTP_400_BAD_REQUEST)