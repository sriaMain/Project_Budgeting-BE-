from django.db import models
from django.core.exceptions import ValidationError


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
    

