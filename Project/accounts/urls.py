# accounts/urls.py
from django.urls import path
from .views import LoginView, OTPRequestView, OTPVerifyView, ResetPasswordView,ResendOTPView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
     path('otp-request/', OTPRequestView.as_view(), name='otp-request'),
    path('verify-otp/', OTPVerifyView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),

]
