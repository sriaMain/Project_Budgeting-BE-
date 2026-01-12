from django.contrib import admin

# Register your models here.
from .models import Invoice, InvoiceItem, InvoicePayment, PurchaseOrder,PurchaseOrderItem,OutgoingPayment
admin.site.register(Invoice)
admin.site.register(InvoiceItem)    
# admin.site.register(InvoiceMilestone)
admin.site.register(InvoicePayment)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
admin.site.register(OutgoingPayment)
