
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.db.models import Sum
from Project.models import Project
from product_group.models import Quote, Product_Services
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.conf import settings
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import F
from django.utils import timezone
from decimal import Decimal
from accounts.models import Vendor




class Invoice(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Issued', 'Issued'),
        ('Partially Paid', 'Partially Paid'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
        ('Cancelled', 'Cancelled'),
    ]

    id = models.BigAutoField(primary_key=True)

    invoice_no = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        db_index=True
    )

    quote = models.ForeignKey(
        Quote,
        on_delete=models.PROTECT,
        related_name='invoices'
    )

    client = models.ForeignKey(
        'client.Company',
        on_delete=models.PROTECT
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Issued'
    )

    issue_date = models.DateField()
    due_date = models.DateField()

    sub_total = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))

    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    balance_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))

    notes = models.TextField(blank=True)
    terms_conditions = models.TextField(blank=True)

    pdf_file = models.FileField(upload_to='invoices/pdfs/', null=True, blank=True)
    sent_date = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices'
    )
    updated_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_invoices'
    )

    # Soft-delete metadata
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_invoices'
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='invoice_total_non_negative'
            ),
            models.CheckConstraint(
                check=models.Q(balance_amount__gte=0),
                name='invoice_balance_non_negative'
            ),
        ]

    def __str__(self):
        return self.invoice_no
    
    def calculate_totals(self):
        self.sub_total = (
            self.items.aggregate(total=Sum('amount'))['total']
            or Decimal("0.00")
        )

        taxable = self.sub_total - self.discount_amount
        self.tax_amount = taxable * (self.tax_percentage / Decimal("100"))
        self.total_amount = taxable + self.tax_amount

        self.paid_amount = (
            self.payments.aggregate(total=Sum('amount'))['total']
            or Decimal("0.00")
        )

        self.balance_amount = self.total_amount - self.paid_amount

    def update_status(self, save=True):
        if self.status == 'Cancelled':
            return

        self.calculate_totals()

        if self.balance_amount <= Decimal("0.00"):
            self.status = 'Paid'
        elif self.paid_amount > Decimal("0.00"):
            self.status = 'Partially Paid'
        elif self.due_date < timezone.now().date():
            self.status = 'Overdue'
        else:
            self.status = 'Issued'

        if save:
            super().save(update_fields=[
                'status',
                'sub_total',
                'tax_amount',
                'total_amount',
                'paid_amount',
                'balance_amount'
            ])

    

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        related_name='items',
        on_delete=models.CASCADE
    )

    product_service = models.ForeignKey(
        Product_Services,
        on_delete=models.PROTECT
    )

    description = models.TextField(blank=True)

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    unit = models.CharField(max_length=20, default='Unit')

    price_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))

    def save(self, *args, **kwargs):
        base = self.quantity * self.price_per_unit
        discount = base * (self.discount_percentage / Decimal("100"))
        self.amount = base - discount
        super().save(*args, **kwargs)



class InvoicePayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Credit Card', 'Credit Card'),
        ('Debit Card', 'Debit Card'),
        ('UPI', 'UPI'),
        ('Cheque', 'Cheque'),
        ('Other', 'Other'),
    ]

    invoice = models.ForeignKey(
        Invoice,
        related_name='payments',
        on_delete=models.PROTECT
    )

    payment_date = models.DateField()

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    reference_no = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    attachment = models.FileField(
        upload_to='invoices/payments/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True
    )

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def clean(self):
        if self.invoice_id:
            self.invoice.calculate_totals()
            if self.amount > self.invoice.balance_amount:
                raise ValidationError(
                    f"Payment amount cannot exceed balance {self.invoice.balance_amount}"
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.update_status()





class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    po_no = models.CharField(max_length=30, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    quote = models.ForeignKey('product_group.Quote', on_delete=models.PROTECT)
    project = models.ForeignKey('Project.Project', on_delete=models.PROTECT)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    issue_date = models.DateField(default=timezone.now)

    sub_total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    created_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True
    )

    def calculate_totals(self):
        self.sub_total = self.items.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        self.total_amount = self.sub_total

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        related_name='items',
        on_delete=models.CASCADE
    )

    quote_item = models.ForeignKey(
        'product_group.QuoteItem',
        on_delete=models.PROTECT
    )

    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_rate = models.DecimalField(max_digits=10, decimal_places=2)

    amount = models.DecimalField(max_digits=15, decimal_places=2)

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.unit_rate
        super().save(*args, **kwargs)


class VendorBill(models.Model):
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partially_paid', 'Partially Paid'),
        ('paid', 'Paid'),
    ]

    bill_no = models.CharField(max_length=50, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT)

    bill_date = models.DateField()
    due_date = models.DateField()

    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=15, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')

    def save(self, *args, **kwargs):
        if not self.pk:
            self.total_amount = self.purchase_order.total_amount
            self.balance_amount = self.total_amount
        super().save(*args, **kwargs)

    def update_status(self):
        self.balance_amount = self.total_amount - self.paid_amount
        if self.balance_amount <= 0:
            self.status = 'paid'
        elif self.paid_amount > 0:
            self.status = 'partially_paid'
        else:
            self.status = 'unpaid'
class OutgoingPayment(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('bank', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
    ]

    vendor_bill = models.ForeignKey(
        VendorBill,
        related_name='payments',
        on_delete=models.PROTECT
    )

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)

    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_no = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        # Ensure amount is Decimal
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        
        if self.amount > self.vendor_bill.balance_amount:
            raise ValidationError("Payment exceeds bill balance")

        super().save(*args, **kwargs)

        VendorBill.objects.filter(
            id=self.vendor_bill_id
        ).update(
            paid_amount=F('paid_amount') + self.amount
        )

        bill = VendorBill.objects.get(id=self.vendor_bill_id)
        bill.update_status()
        bill.save()
# models.py
from django.db import models
from cloudinary.models import CloudinaryField

class ProjectAttachment(models.Model):

    CATEGORY_CHOICES = (
        ("contract", "Contract"),
        ("quote", "Quote"),
        ("invoice", "Invoice"),
        ("bill", "Bill"),
        ("design", "Design"),
        ("other", "Other"),
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    file = CloudinaryField(
        "attachment",
        folder="project_attachments",
        resource_type="raw",
        type="upload"   # 🔥 PUBLIC FILE
)


    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    file_type = models.CharField(max_length=100)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="other"
    )

    uploaded_by = models.ForeignKey(
        "accounts.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file_name





from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum
from django.core.validators import MinValueValidator
import uuid

class Expense(models.Model):

    CATEGORY_CHOICES = [
        ('rent', 'Rent'),
        ('travel', 'Travel'),
        ('food', 'Food'),
        ('internet', 'Internet'),
        ('electricity', 'Electricity'),
        ('software', 'Software'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ]

    expense_no = models.CharField(
        max_length=40,
        unique=True,
        editable=False,
        db_index=True
    )

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)

    project = models.ForeignKey(
        'Project.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )

    vendor = models.ForeignKey(
        'accounts.Vendor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    expense_date = models.DateField(default=timezone.localdate)

    description = models.TextField()

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    created_by = models.ForeignKey(
        'accounts.Account',
        on_delete=models.SET_NULL,
        null=True,
        related_name='expenses_created'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return self.expense_no

    # 🔐 MODEL VALIDATION
    def clean(self):
        if self.expense_date > timezone.localdate():
            raise ValidationError("Expense date cannot be in the future")

        if self.pk and self.total_paid() > self.amount:
            raise ValidationError("Expense amount cannot be less than already paid amount")

    def save(self, *args, **kwargs):
        self.full_clean()

        if not self.expense_no:
            self.expense_no = f"EXP-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        super().save(*args, **kwargs)

    # 🔥 DERIVED FINANCIAL STATE
    def total_paid(self):
        return self.payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')

    def balance_amount(self):
        balance = self.amount - self.total_paid()
        return max(balance, Decimal('0.00'))

    def is_fully_paid(self):
        return self.balance_amount() == Decimal('0.00')


class ExpensePayment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ('bank', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cash', 'Cash'),
        ('card', 'Card'),
    ]

    expense = models.ForeignKey(
        Expense,
        related_name='payments',
        on_delete=models.PROTECT
    )

    payment_date = models.DateField(default=timezone.localdate)

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference_no = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.expense.is_fully_paid():
            raise ValidationError("Expense is already fully paid")

        if self.amount > self.expense.balance_amount():
            raise ValidationError("Payment exceeds expense balance")

        super().save(*args, **kwargs)
