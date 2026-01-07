from django.contrib import admin

# Register your models here.
from .models import ProductGroup, Product_Services,Quote, QuoteItem


admin.site.register(ProductGroup)
admin.site.register(Product_Services)
admin.site.register(Quote)
admin.site.register(QuoteItem)