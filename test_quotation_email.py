"""
Test script for quotation status change email notifications.

This script helps you test the email notification system by:
1. Creating a test quotation
2. Updating its status
3. Verifying that email notifications are sent

Usage:
    python manage.py shell < test_quotation_email.py
    
Or in Django shell:
    exec(open('test_quotation_email.py').read())
"""

from product_group.models import Quote, QuoteItem, Product_Services, ProductGroup
from client.models import Company, POC
from accounts.models import Account
from datetime import date, timedelta

print("\n" + "="*60)
print("Testing Quotation Status Change Email Notifications")
print("="*60 + "\n")

# Get or create test data
print("1. Setting up test data...")

# Get or create a client company
company, created = Company.objects.get_or_create(
    company_name="Test Company Ltd",
    defaults={
        'mobile_number': '1234567890',
        'email': 'testcompany@example.com',
        'street_address': '123 Test St',
        'city': 'Test City',
        'state': 'Test State',
        'country': 'Test Country'
    }
)
print(f"   {'Created' if created else 'Found'} company: {company.company_name}")

# Get or create a POC
poc, created = POC.objects.get_or_create(
    company=company,
    poc_name="Test POC",
    defaults={
        'designation': 'Manager',
        'poc_mobile': '9876543210',
        'poc_email': 'testpoc@example.com'  # Change this to your test email
    }
)
print(f"   {'Created' if created else 'Found'} POC: {poc.poc_name} ({poc.poc_email})")

# Get an author (you can change this to a specific user)
try:
    author = Account.objects.filter(email__isnull=False).first()
    if not author:
        print("   WARNING: No user with email found. Email to author won't be sent.")
    else:
        print(f"   Found author: {author.get_full_name()} ({author.email})")
except Exception as e:
    print(f"   ERROR getting author: {e}")
    author = None

# Get or create a product group and product
product_group, _ = ProductGroup.objects.get_or_create(
    product_group_name="Test Services",
    defaults={'description': 'Test product group'}
)

product, _ = Product_Services.objects.get_or_create(
    product_service_name="Test Service",
    defaults={
        'product_group': product_group,
        'description': 'Test product for quotations'
    }
)
print(f"   Found product: {product.product_service_name}")

# Create or get a test quotation
print("\n2. Creating test quotation...")
quote, created = Quote.objects.get_or_create(
    quote_name="Test Quotation - Email Notification",
    defaults={
        'date_of_issue': date.today(),
        'due_date': date.today() + timedelta(days=30),
        'status': 'Oppurtunity',
        'client': company,
        'poc': poc,
        'author': author,
        'created_by': author,
        'sub_total': 10000.00,
        'total_amount': 11800.00,  # Including 18% tax
        'tax_percentage': 18.00,
    }
)

if created:
    # Add a quote item
    QuoteItem.objects.create(
        quote=quote,
        product_service=product,
        description="Test service item",
        quantity=100,
        unit='hours',
        price_per_unit=100.00,
        cost=80.00
    )
    print(f"   Created quote: #{quote.quote_no} - {quote.quote_name}")
else:
    print(f"   Found existing quote: #{quote.quote_no} - {quote.quote_name}")

print(f"   Current status: {quote.status}")

# Test status change
print("\n3. Testing status change...")
print(f"   Changing status from '{quote.status}' to 'Scoping'...")

old_status = quote.status
quote.status = 'Scoping'
quote.save()

print(f"   ✓ Status changed successfully!")
print(f"   Email notification should be sent to:")
if poc:
    print(f"     - POC: {poc.poc_email}")
if company:
    print(f"     - Client: {company.email}")
if author:
    print(f"     - Author: {author.email}")

print("\n4. Testing another status change (to Confirmed)...")
quote.status = 'Confirmed'
quote.save()
print(f"   ✓ Changed status to 'Confirmed'")

print("\n" + "="*60)
print("Test complete!")
print("="*60)
print("\nNOTE: Check your email inbox or console (if using console backend)")
print("to verify that notifications were sent.\n")
print("If emails are not arriving, check:")
print("1. EMAIL_BACKEND setting in settings.py")
print("2. Celery is running (in a separate terminal)")
print("3. Redis is running (celery broker)")
print("4. Email addresses are valid")
print("\nQuote ID for reference:", quote.pk)
