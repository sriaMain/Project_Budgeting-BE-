from django.db import models


class CompanyTag(models.Model):
   
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Company(models.Model):
    # General Information

    company_name = models.CharField(max_length=255, unique=True)
    mobile_number = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    gstin = models.CharField(max_length=20, blank=True)

    # Address
    street_address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    
    # poc_name = models.CharField(max_length=150, blank=True)
    # poc_designation = models.CharField(max_length=100, blank=True)
    # poc_mobile = models.CharField(max_length=20, blank=True)
    # poc_email = models.EmailField(blank=True)

    # Tags
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