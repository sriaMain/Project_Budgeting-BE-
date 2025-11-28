from django.contrib import admin

# Register your models here.
from .models import ProductGroup, Product_Services

admin.site.register(ProductGroup)
admin.site.register(Product_Services)