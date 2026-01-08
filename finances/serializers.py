# serializers.py
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime, date
from .models import Invoice, InvoiceItem, InvoicePayment



class InvoiceItemSerializer(serializers.ModelSerializer):
    product_service_id = serializers.IntegerField(
        source='product_service.id', read_only=True
    )
    product_service = serializers.CharField(
        source='product_service.product_service_name', read_only=True
    )

    class Meta:
        model = InvoiceItem
        fields = [
            'id',
            'product_service_id',
            'product_service',
            'description',
            'quantity',
            'unit',
            'price_per_unit',
            'discount_percentage',
            'amount',
        ]
        read_only_fields = ['amount']


    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value

    def validate_price_per_unit(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value

    def validate_discount_percentage(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                "Discount percentage must be between 0 and 100"
            )
        return value



class InvoiceItemCreateSerializer(serializers.Serializer):
    """Serializer for creating invoice items"""
    product_service_id = serializers.IntegerField()
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    unit = serializers.CharField(max_length=20, default='Unit')
    price_per_unit = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), min_value=Decimal('0'), max_value=Decimal('100'))





class InvoicePaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment records"""

    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True
    )

   
    created_by_name = serializers.SerializerMethodField()
    invoice_no = serializers.CharField(source='invoice.invoice_no', read_only=True)

    class Meta:
        model = InvoicePayment
        fields = [
            'id',
            'invoice',
            'invoice_no',

            'payment_date',
            'amount',
            # 'payment_method',
            'payment_method_display',
            'reference_no',
            'notes',
            'attachment',

            'created_at',
            'created_by',
            'created_by_name'
        ]
        read_only_fields = ['invoice', 'created_at', 'created_by', 'created_by_name']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than 0"
            )
        return value

    def validate_payment_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "Payment date cannot be in the future"
            )
        return value

 
  


class RecordPaymentSerializer(serializers.Serializer):
    """Serializer for recording a payment"""
    invoice_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    payment_date = serializers.DateField()
    payment_method = serializers.ChoiceField(choices=InvoicePayment.PAYMENT_METHOD_CHOICES)
    reference_no = serializers.CharField(max_length=100, required=False, allow_blank=True)
    # milestone_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    attachment = serializers.FileField(required=False, allow_null=True)
    
    def validate_payment_date(self, value):
        """Validate payment date"""
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d').date()
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD")
        
        if value > timezone.now().date():
            raise serializers.ValidationError("Payment date cannot be in the future")
        
        return value




class InvoiceListSerializer(serializers.ModelSerializer):
    """Compact serializer for invoice list view"""
    client_id = serializers.IntegerField(source='client.id', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_email = serializers.SerializerMethodField()
    quote_no = serializers.CharField(source='quote.quote_no', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status = serializers.SerializerMethodField()
    payment_percentage = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_no',
            'client_id',
            'client_name',
            'client_email',
            'quote_no',
            'status',
            'status_display',
            'issue_date',
            'due_date',
            'days_until_due',
            'is_overdue',
            'total_amount',
            'paid_amount',
            'balance_amount',
            'payment_status',
            'payment_percentage',
            'created_at'
        ]
    
    def get_client_email(self, obj):
        """Get client email if available"""
        return getattr(obj.client, 'email', '')
    
    def get_payment_status(self, obj):
        """Get human-readable payment status"""
        if obj.balance_amount == 0:
            return 'Fully Paid'
        elif obj.paid_amount > 0:
            percentage = (obj.paid_amount / obj.total_amount) * 100
            return f'{percentage:.1f}% Paid'
        return 'Unpaid'
    
    def get_payment_percentage(self, obj):
        """Get payment percentage as number"""
        if obj.total_amount == 0:
            return 0
        return float((obj.paid_amount / obj.total_amount) * 100)
    
    def get_days_until_due(self, obj):
        """Calculate days until due date"""
        delta = obj.due_date - timezone.now().date()
        return delta.days
    
    def get_is_overdue(self, obj):
        """Check if invoice is overdue"""
        return obj.status == 'Overdue' or (
            obj.due_date < timezone.now().date() and 
            obj.balance_amount > 0 and 
            obj.status not in ['Paid', 'Cancelled']
        )



class InvoiceDetailSerializer(serializers.ModelSerializer):

    client_id = serializers.IntegerField(source='client.id', read_only=True)
    client_name = serializers.CharField(source='client.company_name', read_only=True)

    quote_id = serializers.IntegerField(source='quote.id', read_only=True)
    quote_no = serializers.CharField(source='quote.quote_no', read_only=True)

    project_id = serializers.IntegerField(source='project.id', read_only=True, allow_null=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)

    status_display = serializers.CharField(source='get_status_display', read_only=True)

    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = InvoicePaymentSerializer(many=True, read_only=True)

    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

    payment_status = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_until_due = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = '__all__'

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() if obj.created_by else None

    def get_updated_by_name(self, obj):
        return obj.updated_by.get_full_name() if obj.updated_by else None

    def get_payment_status(self, obj):
        if obj.balance_amount <= 0:
            return 'Fully Paid'
        if obj.paid_amount > 0:
            return 'Partially Paid'
        return 'Unpaid'

    def get_is_overdue(self, obj):
        return (
            obj.due_date < timezone.now().date()
            and obj.balance_amount > 0
            and obj.status not in ['Paid', 'Cancelled']
        )

    def get_days_until_due(self, obj):
        return (obj.due_date - timezone.now().date()).days

# ==============================================================================
# INVOICE GENERATION SERIALIZER
# ==============================================================================

# class GenerateInvoiceSerializer(serializers.Serializer):
#     """Serializer for generating invoice from quote"""
#     quote_id = serializers.IntegerField()
#     due_days = serializers.IntegerField(default=30, min_value=1, max_value=365)
#     # include_milestones = serializers.BooleanField(default=False)
#     # milestones = serializers.ListField(
#     #     child=MilestoneCreateSerializer(),
#     #     required=False,
#     #     allow_empty=True
#     # )
#     product_service_id = serializers.IntegerField(
#         required=False,
#         allow_null=True
#     )
#     product_service_ids = serializers.ListField(
#         child=serializers.IntegerField(),
#         required=False,
#         allow_empty=True
#     )
#     product_group_id = serializers.IntegerField(
#         required=False,
#         allow_null=True
#     )
#     notes = serializers.CharField(required=False, allow_blank=True)
#     terms_conditions = serializers.CharField(required=False, allow_blank=True)
    
#     def validate_milestones(self, value):
#         """Validate milestones sum to 100%"""
#         if not value:
#             return value
        
#         total_percentage = sum(Decimal(str(m['percentage'])) for m in value)
        
#         if total_percentage != 100:
#             raise serializers.ValidationError(
#                 f"Total milestone percentages must equal 100%, got {total_percentage}%"
#             )
        
#         return value
    
    

#     def validate(self, data):
#         # Ensure only one of product_service_id, product_service_ids, product_group_id is provided
#         ps_single = 'product_service_id' in data and data.get('product_service_id') is not None
#         ps_list = 'product_service_ids' in data and data.get('product_service_ids')
#         pg = 'product_group_id' in data and data.get('product_group_id') is not None

#         provided = sum(bool(x) for x in [ps_single, bool(ps_list), pg])
#         if provided > 1:
#             raise serializers.ValidationError(
#                 "Provide only one of product_service_id, product_service_ids, or product_group_id"
#             )

#         return data
class GenerateInvoiceSerializer(serializers.Serializer):
    quote_id = serializers.IntegerField()
    due_days = serializers.IntegerField(default=30, min_value=1, max_value=365)

    product_service_id = serializers.IntegerField(required=False, allow_null=True)
    product_service_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    # 🔥 SUPPORT BOTH
    product_group_id = serializers.IntegerField(required=False, allow_null=True)
    product_group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    # NEW: Select specific quote items by their IDs
    quote_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )

    notes = serializers.CharField(required=False, allow_blank=True)
    terms_conditions = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        provided = sum(bool(x) for x in [
            data.get('product_service_id'),
            data.get('product_service_ids'),
            data.get('product_group_id'),
            data.get('product_group_ids'),
            data.get('quote_item_ids'),
        ])

        if provided > 1:
            raise serializers.ValidationError(
                "Provide only ONE filter (service OR group OR quote_items)"
            )

        return data



# ==============================================================================
# EMAIL SERIALIZER
# ==============================================================================

class SendInvoiceEmailSerializer(serializers.Serializer):
    """Serializer for sending invoice via email"""
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1
    )
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    include_pdf = serializers.BooleanField(default=True)
    cc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True
    )
    
    def validate_recipient_emails(self, value):
        """Remove duplicates from recipient emails"""
        return list(set(value))
    
    def validate_cc_emails(self, value):
        """Remove duplicates from CC emails"""
        if value:
            return list(set(value))
        return []


# ==============================================================================
# CANCEL INVOICE SERIALIZER
# ==============================================================================

class CancelInvoiceSerializer(serializers.Serializer):
    """Serializer for cancelling an invoice"""
    reason = serializers.CharField(required=True, min_length=10)
    
    def validate_reason(self, value):
        """Validate cancellation reason"""
        if not value.strip():
            raise serializers.ValidationError("Cancellation reason cannot be empty")
        
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Cancellation reason must be at least 10 characters")
        
        return value.strip()


# ==============================================================================
# STATISTICS SERIALIZER
# ==============================================================================

class InvoiceStatsSerializer(serializers.Serializer):
    """Serializer for invoice statistics"""
    total_invoices = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    
    status_breakdown = serializers.DictField()
    payment_method_breakdown = serializers.DictField()
    
    recent_invoices = InvoiceListSerializer(many=True)
    upcoming_due = InvoiceListSerializer(many=True)
    
    # Monthly stats (optional)
    monthly_revenue = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    monthly_count = serializers.IntegerField(required=False)


# ==============================================================================
# UPDATE INVOICE SERIALIZER
# ==============================================================================

class UpdateInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for updating invoice details"""
    
    class Meta:
        model = Invoice
        fields = [
            'due_date',
            'notes',
            'terms_conditions',
            'discount_amount',
            'tax_percentage'
        ]
    
    def validate_due_date(self, value):
        """Validate due date"""
        if value < self.instance.issue_date:
            raise serializers.ValidationError("Due date cannot be before issue date")
        return value
    
    def validate_discount_amount(self, value):
        """Validate discount amount"""
        if value < 0:
            raise serializers.ValidationError("Discount amount cannot be negative")
        
        if self.instance and value > self.instance.sub_total:
            raise serializers.ValidationError("Discount cannot exceed subtotal")
        
        return value
    
    def validate_tax_percentage(self, value):
        """Validate tax percentage"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax percentage must be between 0 and 100")
        return value





from rest_framework import serializers
from .models import *

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = '__all__'


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'


class VendorBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorBill
        read_only_fields = (
            'total_amount',
            'paid_amount',
            'balance_amount',
            'status',
        )
        fields = '__all__'


class OutgoingPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingPayment
        fields = '__all__'
