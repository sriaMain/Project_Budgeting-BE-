from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

class CompanyTag(models.Model):
   
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

gstin_validator = RegexValidator(
    regex=r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
    message="Enter a valid GSTIN (15 characters)."
)

mobile_validator = RegexValidator(
    regex=r"^[0-9+\-\s()]{7,10}$",
    message="Enter a valid mobile number."
)
class Company(models.Model):
    # General Information

    company_name = models.CharField(max_length=255, unique=True)
    mobile_number = models.CharField(
        max_length=20,
        validators=[mobile_validator]
    )
    email = models.EmailField(unique=True)
    gstin = models.CharField(
        max_length=15,
        blank=True,
        validators=[gstin_validator]
    )

    # Address
    street_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    tags = models.ManyToManyField(
        CompanyTag,
        related_name="companies",
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name
    def clean(self):
        if self.gstin and len(self.gstin) != 15:
            raise ValidationError({"gstin": "GSTIN must be exactly 15 characters."})

    

class POC(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='pocs')
    poc_name = models.CharField(max_length=150)
    designation = models.CharField(max_length=100)
    poc_mobile = models.CharField(max_length=15)
    poc_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('company', 'poc_name', 'poc_mobile', 'poc_email')

    def __str__(self):
        return f"{self.poc_name} ({self.company.company_name})"