# serializers.py
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime, date
from .models import Invoice, InvoiceItem, InvoicePayment


# ==============================================================================
# INVOICE ITEM SERIALIZERS
# ==============================================================================

class InvoiceItemSerializer(serializers.ModelSerializer):
    """Serializer for invoice line items"""
    product_service_id = serializers.IntegerField(source='product_service.id', read_only=True)
    product_service_name = serializers.CharField(source='product_service.name', read_only=True)
    product_service_code = serializers.CharField(source='product_service.code', read_only=True, required=False)
    
    class Meta:
        model = InvoiceItem
        fields = [
            'id',
            'product_service',
            'product_service_id',
            'product_service_name',
            'product_service_code',
            'description',
            'quantity',
            'unit',
            'price_per_unit',
            'discount_percentage',
            'amount'
        ]
        read_only_fields = ['amount']
    
    def validate_quantity(self, value):
        """Validate quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate_price_per_unit(self, value):
        """Validate price is not negative"""
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative")
        return value
    
    def validate_discount_percentage(self, value):
        """Validate discount percentage is between 0 and 100"""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount percentage must be between 0 and 100")
        return value


class InvoiceItemCreateSerializer(serializers.Serializer):
    """Serializer for creating invoice items"""
    product_service_id = serializers.IntegerField()
    description = serializers.CharField(required=False, allow_blank=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    unit = serializers.CharField(max_length=20, default='Unit')
    price_per_unit = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'))
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'), min_value=Decimal('0'), max_value=Decimal('100'))


# ==============================================================================
# INVOICE MILESTONE SERIALIZERS
# ==============================================================================

# class InvoiceMilestoneSerializer(serializers.ModelSerializer):
#     """Serializer for payment milestones"""
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
#     paid_amount = serializers.SerializerMethodField()
#     remaining_amount = serializers.SerializerMethodField()
#     is_overdue = serializers.SerializerMethodField()
    
#     class Meta:
#         model = InvoiceMilestone
#         fields = [
#             'id',
#             'invoice',
#             'milestone_no',
#             'title',
#             'description',
#             'due_date',
#             'amount',
#             'percentage',
#             'status',
#             'status_display',
#             'paid_amount',
#             'remaining_amount',
#             'is_overdue',
#             'created_at'
#         ]
#         read_only_fields = ['invoice', 'milestone_no', 'status', 'created_at']
    
#     def get_paid_amount(self, obj):
#         """Calculate total paid amount for this milestone"""
#         return sum(payment.amount for payment in obj.payments.all())
    
#     def get_remaining_amount(self, obj):
#         """Calculate remaining amount for this milestone"""
#         paid = self.get_paid_amount(obj)
#         return obj.amount - paid
    
#     def get_is_overdue(self, obj):
#         """Check if milestone is overdue"""
#         if obj.status == 'Paid':
#             return False
#         return obj.due_date < timezone.now().date()
    
#     def validate_percentage(self, value):
#         """Validate percentage is within 0-100"""
#         if value < 0 or value > 100:
#             raise serializers.ValidationError("Percentage must be between 0 and 100")
#         return value
    
#     def validate_due_date(self, value):
#         """Validate due date is not in the past (only for creation)"""
#         if not self.instance and value < timezone.now().date():
#             raise serializers.ValidationError("Due date cannot be in the past")
#         return value
    
#     def validate_amount(self, value):
#         """Validate amount is positive"""
#         if value <= 0:
#             raise serializers.ValidationError("Amount must be greater than 0")
#         return value


# class MilestoneCreateSerializer(serializers.Serializer):
#     """Serializer for creating milestones during invoice generation"""
#     title = serializers.CharField(max_length=200)
#     description = serializers.CharField(required=False, allow_blank=True)
#     percentage = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal('0.01'), max_value=Decimal('100'))
#     due_date = serializers.DateField()
    
#     def validate_due_date(self, value):
#         """Validate due date"""
#         if isinstance(value, str):
#             try:
#                 value = datetime.strptime(value, '%Y-%m-%d').date()
#             except ValueError:
#                 raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD")
        
#         if value < timezone.now().date():
#             raise serializers.ValidationError("Due date cannot be in the past")
        
#         return value



class InvoicePaymentSerializer(serializers.ModelSerializer):
    """Serializer for payment records"""

    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True
    )

    # # ✅ ACCEPT milestone_id as input
    # milestone_id = serializers.PrimaryKeyRelatedField(
    #     source='milestone',
    #     queryset=InvoiceMilestone.objects.all(),
    #     required=False,
    #     allow_null=True
    # )

    # milestone_title = serializers.CharField(
    #     source='milestone.title',
    #     read_only=True
    # )

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
            'payment_method',
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


# ==============================================================================
# INVOICE LIST SERIALIZERS
# ==============================================================================

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


# ==============================================================================
# INVOICE DETAIL SERIALIZER
# ==============================================================================

# class InvoiceDetailSerializer(serializers.ModelSerializer):
#     """Detailed serializer for invoice with all related data"""
#     # Client information
#     client_id = serializers.IntegerField(source='client.id', read_only=True)
#     client_name = serializers.CharField(source='client.name', read_only=True)
#     client_details = serializers.SerializerMethodField()
    
#     # Quote information
#     quote_id = serializers.IntegerField(source='quote.id', read_only=True)
#     quote_no = serializers.CharField(source='quote.quote_no', read_only=True)
    
#     # Project information
#     project_id = serializers.IntegerField(source='project.id', read_only=True, allow_null=True)
#     project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    
#     # Status
#     status_display = serializers.CharField(source='get_status_display', read_only=True)
    
#     # Related data
#     items = InvoiceItemSerializer(many=True, read_only=True)
#     payments = InvoicePaymentSerializer(many=True, read_only=True)
#     # milestones = InvoiceMilestoneSerializer(many=True, read_only=True)
    
#     # Metadata
#     created_by_name = serializers.SerializerMethodField()
#     updated_by_name = serializers.SerializerMethodField()
    
#     # Computed fields
#     payment_status = serializers.SerializerMethodField()
#     is_overdue = serializers.SerializerMethodField()
#     days_until_due = serializers.SerializerMethodField()
#     has_milestones = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Invoice
#         fields = [
#             # Basic info
#             'id', 'invoice_no', 'status', 'status_display',
            
#             # Related entities
#             'quote', 'quote_id', 'quote_no',
#             'client', 'client_id', 'client_name', 'client_details',
#             'project', 'project_id', 'project_name',
            
#             # Dates
#             'issue_date', 'due_date', 'sent_date',
#             'days_until_due', 'is_overdue',
            
#             # Financial
#             'sub_total', 'tax_percentage', 'tax_amount',
#             'discount_amount', 'total_amount', 'paid_amount', 'balance_amount',
#             'payment_status',
            
#             # Content
#             'notes', 'terms_conditions',
            
#             # Related data
#             'items', 'payments', 'milestones', 'has_milestones',
            
#             # Files
#             'pdf_file',
            
#             # Metadata
#             'created_at', 'updated_at',
#             'created_by', 'created_by_name',
#             'updated_by', 'updated_by_name'
#         ]
#         read_only_fields = [
#             'invoice_no', 'sub_total', 'tax_amount', 'total_amount',
#             'paid_amount', 'balance_amount', 'created_at', 'updated_at',
#             'sent_date'
#         ]
    
#     def get_client_details(self, obj):
#         """Get detailed client information"""
#         client = obj.client
#         return {
#             'id': client.id,
#             'name': client.company_name,
#             'email': getattr(client, 'email', ''),
#             'phone': getattr(client, 'phone', ''),
#             'address': getattr(client, 'address', ''),
#             'city': getattr(client, 'city', ''),
#             'state': getattr(client, 'state', ''),
#             'country': getattr(client, 'country', ''),
#             'postal_code': getattr(client, 'postal_code', ''),
#         }
    
#     def get_created_by_name(self, obj):
#         """Get creator's name"""
#         if obj.created_by:
#             return obj.created_by.get_full_name() or obj.created_by.username
#         return None
    
#     def get_updated_by_name(self, obj):
#         """Get updater's name"""
#         if obj.updated_by:
#             return obj.updated_by.get_full_name() or obj.updated_by.username
#         return None
    
#     def get_payment_status(self, obj):
#         """Get payment status description"""
#         if obj.balance_amount == 0:
#             return 'Fully Paid'
#         elif obj.paid_amount > 0:
#             percentage = (obj.paid_amount / obj.total_amount) * 100
#             return f'{percentage:.1f}% Paid'
#         return 'Unpaid'
    
#     def get_is_overdue(self, obj):
#         """Check if invoice is overdue"""
#         return obj.status == 'Overdue' or (
#             obj.due_date < timezone.now().date() and 
#             obj.balance_amount > 0 and 
#             obj.status not in ['Paid', 'Cancelled']
#         )
    
#     def get_days_until_due(self, obj):
#         """Calculate days until/since due date"""
#         delta = obj.due_date - timezone.now().date()
#         return delta.days
    
#     def get_has_milestones(self, obj):
#         """Check if invoice has milestones"""
#         return obj.milestones.exists()


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for invoice with all related data"""

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
        fields = [
            'id',
            'invoice_no',
            'status',
            'status_display',

            'quote',
            'quote_id',
            'quote_no',

            'client',
            'client_id',
            'client_name',

            'project',
            'project_id',
            'project_name',

            'issue_date',
            'due_date',
            'sent_date',

            'days_until_due',
            'is_overdue',

            'sub_total',
            'tax_percentage',
            'tax_amount',
            'discount_amount',
            'total_amount',
            'paid_amount',
            'balance_amount',
            'payment_status',

            'notes',
            'terms_conditions',

            'items',
            'payments',

            'pdf_file',

            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'updated_by',
            'updated_by_name',
        ]

        read_only_fields = [
            'invoice_no',
            'sub_total',
            'tax_amount',
            'total_amount',
            'paid_amount',
            'balance_amount',
            'created_at',
            'updated_at',
            'sent_date',
        ]

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

class GenerateInvoiceSerializer(serializers.Serializer):
    """Serializer for generating invoice from quote"""
    quote_id = serializers.IntegerField()
    due_days = serializers.IntegerField(default=30, min_value=1, max_value=365)
    include_milestones = serializers.BooleanField(default=False)
    # milestones = serializers.ListField(
    #     child=MilestoneCreateSerializer(),
    #     required=False,
    #     allow_empty=True
    # )
    notes = serializers.CharField(required=False, allow_blank=True)
    terms_conditions = serializers.CharField(required=False, allow_blank=True)
    
    def validate_milestones(self, value):
        """Validate milestones sum to 100%"""
        if not value:
            return value
        
        total_percentage = sum(Decimal(str(m['percentage'])) for m in value)
        
        if total_percentage != 100:
            raise serializers.ValidationError(
                f"Total milestone percentages must equal 100%, got {total_percentage}%"
            )
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        if data.get('include_milestones') and not data.get('milestones'):
            raise serializers.ValidationError({
                'milestones': 'Milestones are required when include_milestones is True'
            })
        
        if not data.get('include_milestones') and data.get('milestones'):
            raise serializers.ValidationError({
                'include_milestones': 'Set include_milestones to True to add milestones'
            })
        
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