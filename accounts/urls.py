# accounts/urls.py
from django.urls import path
from .views import (LoginView, OTPRequestView, OTPVerifyView, ResetPasswordView,ResendOTPView
                    ,LogoutView, RefreshTokenCookieView, UserCreateView, UserListView, UserDetailVieW)
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('otp-request/', OTPRequestView.as_view(), name='otp-request'),
    path('verify-otp/', OTPVerifyView.as_view(), name='verify-otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    # path("session-check/", SessionCheckView.as_view(), name="session-check"),
    path('refresh/', RefreshTokenCookieView.as_view(), name='token_refresh'),

    # 3. Check Access Token Expiry Time
    # path('token/expiry/', AccessTokenExpiryView.as_view(), name='token_expiry'),

    # 4. Logout (delete both cookies)
    path('logout/', LogoutView.as_view(), name='logout'),
    path("users/create/", UserCreateView.as_view(), name="user-create"),
    path("users/", UserListView.as_view(), name="user-detail"),
    path("users/<int:id>/", UserDetailVieW.as_view(), name="user-detail"),

]
