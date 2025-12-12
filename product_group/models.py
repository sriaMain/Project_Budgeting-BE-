from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


# Create your models here.
class ProductGroup(models.Model):
    product_group_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='product_groups_created', null=True)
    modified_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='product_groups_updated', null=True)

    def __str__(self):
        return self.product_group_name
    
    def clean(self):
        name = self.product_group_name.strip().lower()
        if ProductGroup.objects.filter(product_group_name__iexact=name).exclude(id=self.id).exists():
            raise ValidationError("Product Group with this name already exists (case insensitive).")

    def save(self, *args, **kwargs):
    # only clean the name if needed
        self.product_group_name = self.product_group_name.strip()
        super().save(*args, **kwargs)



class Product_Services(models.Model):
    # UNIT_CHOICES = [
    #     ('pieces', 'Pieces'),
    #     ('hours', 'Hours'),
    #     ('days', 'Days'),
    #     ('minutes', 'Minutes'),
    # ]
    # unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pieces')
    product_service_name = models.CharField(max_length=100, unique=True)
    product_group = models.ForeignKey(ProductGroup, on_delete=models.SET_NULL, related_name='products_services', null=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='products_services_created', null=True)
    modified_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='products_services_updated', null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.product_service_name
    

class Quote(models.Model):
    """
    This model stores the main details of the quote (the header).
    """
    STATUS_CHOICES = [
        ('Oppurtunity', 'Oppurtunity'),
        ('Scoping', 'Scoping'),
        ('Proposal', 'Proposal'),
        ('Confirmed', 'Confirmed'),
    ]
    quote_no = models.AutoField(primary_key=True)
    quote_name = models.CharField(max_length=100)
    date_of_issue = models.DateField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Oppurtunity')

    
    # Link to the Client and POC models
    client = models.ForeignKey('client.Company', on_delete=models.SET_NULL, related_name='quotes', null=True)
    poc = models.ForeignKey('client.POC', on_delete=models.SET_NULL, related_name='quotes', null=True)
    
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='authored_quotes', null=True)
    
    # Summary fields can be calculated or stored
    sub_total = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Cost and invoicing summary
    total_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    in_house_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    outsourced_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    invoiced_sum = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    to_be_invoiced_sum = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='created_quotes', null=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name='updated_quotes', null=True)

    def __str__(self):
        return f"Quote {self.quote_no} - {self.quote_name}"


class QuoteItem(models.Model):
    """
    This new model stores each individual line item for a quote.
    """
    UNIT_CHOICES = [
        ('pieces', 'Pieces'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('minutes', 'Minutes'),
    ]
    # Link each item back to its parent Quote
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name='items')
    
    # The product/service chosen for this line
    product_service = models.ForeignKey(Product_Services, on_delete=models.SET_NULL, null=True)
    
    # You can override the default description
    description = models.TextField(blank=True)
    
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='pieces')
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # This can be calculated automatically on save
    amount = models.DecimalField(max_digits=15, decimal_places=2, editable=False)

    # Optional tracking numbers
    po_number = models.CharField(max_length=50, blank=True, null=True)
    bill_number = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        # Automatically calculate the amount before saving
        self.amount = self.quantity * self.price_per_unit
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Item for Quote {self.quote.quote_no}: {self.product_service.product_service_name}"
