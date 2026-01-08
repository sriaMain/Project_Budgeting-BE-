from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

@shared_task
def send_quote_email(subject, message, recipient_email):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [recipient_email],
        fail_silently=False,
    )

@shared_task
def send_quotation_status_change_email(quote_id, old_status, new_status):
    """
    Send email notification when quotation status changes.
    Sends to: Client POC, Quote Author, and Project Manager (if assigned)
    """
    from .models import Quote
    
    try:
        quote = Quote.objects.select_related(
            'client', 'poc', 'author'
        ).get(pk=quote_id)
    except Quote.DoesNotExist:
        return
    
    # Collect recipients
    recipients = []
    
    # Add quote creator/author email
    if quote.author and quote.author.email:
        recipients.append(quote.author.email)
    
    # Add created_by if different from author
    if quote.created_by and quote.created_by.email and quote.created_by.email not in recipients:
        recipients.append(quote.created_by.email)
    
    # Add admin users (superusers)
    from accounts.models import Account
    admin_users = Account.objects.filter(is_superuser=True, email__isnull=False)
    for admin in admin_users:
        if admin.email and admin.email not in recipients:
            recipients.append(admin.email)
    
    if not recipients:
        return
    
    # Prepare email context
    total_amount_display = f"{quote.total_amount:.2f}".lstrip('$')

    context = {
        'quote': quote,
        'old_status': old_status,
        'new_status': new_status,
        'quote_name': quote.quote_name,
        'quote_no': quote.quote_no,
        'client_name': quote.client.company_name if quote.client else 'N/A',
        'total_amount_display': total_amount_display,
        'date_of_issue': quote.date_of_issue,
        'due_date': quote.due_date,
    }
    
    # Create subject based on status
    subject = f"Quotation #{quote.quote_no} Status Changed: {new_status}"
    
    # Render HTML email
    html_message = render_to_string('emails/quotation_status_change.html', context)
    plain_message = strip_tags(html_message)
    
    # Send email
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
    except Exception as e:
        # Log the error but don't raise to avoid breaking the main process
        print(f"Error sending quotation status change email: {str(e)}")
        return False
    
    return True