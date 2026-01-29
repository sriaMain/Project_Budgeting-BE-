from django.contrib import admin

# Register your models here.
from .models import Invoice, InvoiceItem, InvoicePayment, PurchaseOrder,PurchaseOrderItem,OutgoingPayment,ProjectAttachment,Expense, ExpensePayment
admin.site.register(Invoice)
admin.site.register(InvoiceItem)    
# admin.site.register(InvoiceMilestone)
admin.site.register(InvoicePayment)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
admin.site.register(OutgoingPayment)
admin.site.register(ProjectAttachment)
from django.contrib import admin
from .models import Expense, ExpensePayment


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_no', 'category', 'amount', 'expense_date')
    search_fields = ('expense_no',)


@admin.register(ExpensePayment)
class ExpensePaymentAdmin(admin.ModelAdmin):
    list_display = ('expense', 'amount', 'payment_method', 'payment_date')
