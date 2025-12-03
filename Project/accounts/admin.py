from django.contrib import admin
from .models import Account, PasswordResetOTP

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'is_active', 'is_staff')
    search_fields = ('username', 'email',)

@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'hash_preview', 'created_at', 'active', 'is_verified')
    list_filter = ('is_used', 'is_verified', 'created_at')
    search_fields = ('user__username',)

    def hash_preview(self, obj):
        return obj.code_hash[:12] + '...'
    hash_preview.short_description = 'OTP hash'

    def active(self, obj):
        return (not obj.is_used) and (not obj.expired())
    active.boolean = True