from django.contrib import admin

# Register your models here.
from .models import PermissionCategory, Permission, Role
admin.site.register(PermissionCategory)
admin.site.register(Permission)
admin.site.register(Role)