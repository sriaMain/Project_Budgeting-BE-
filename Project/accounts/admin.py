from django.contrib import admin
from .models import Account,PasswordResetOTP


# Register your models here.

admin.site.register(Account)
admin.site.register(PasswordResetOTP)