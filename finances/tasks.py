from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import PurchaseOrder
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import Invoice
from .services import InvoicePDFService

@shared_task
def send_invoice_status_change_email(invoice_id, old_status, new_status):
    from finances.models import Invoice
    from accounts.models import Account
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings

    try:
        invoice = Invoice.objects.select_related(
            'client', 'created_by'
        ).get(pk=invoice_id)
    except Invoice.DoesNotExist:
        return

    recipients = []

    if invoice.client and invoice.client.email:
        recipients.append(invoice.client.email)

    if invoice.created_by and invoice.created_by.email:
        recipients.append(invoice.created_by.email)

    admins = Account.objects.filter(is_superuser=True, email__isnull=False)
    recipients.extend([a.email for a in admins if a.email])

    recipients = list(set(recipients))
    if not recipients:
        return

    context = {
        'invoice': invoice,
        'old_status': old_status,
        'new_status': new_status,
        'invoice_no': invoice.invoice_no,
        'total_amount': invoice.total_amount,
        'balance_amount': invoice.balance_amount,
        'due_date': invoice.due_date,
    }

    subject = f"Invoice {invoice.invoice_no} Status Changed: {new_status}"

    html_message = render_to_string(
        'emails/invoice_status_change.html', context
    )
    plain_message = strip_tags(html_message)

    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    email.attach_alternative(html_message, "text/html")
    email.send(fail_silently=False)



@shared_task
def send_invoice_email(invoice_id):
    invoice = Invoice.objects.select_related("client", "created_by").get(pk=invoice_id)

    invoice_link = f"{settings.FRONTEND_BASE_URL}/invoices/{invoice.id}/"

    html_body = render_to_string(
        "emails/invoice_email.html",
        {
            "invoice": invoice,
            "invoice_link": invoice_link,
            "sender_name": "Accounts Team",
        },
    )

    email = EmailMultiAlternatives(
        subject=f"Invoice {invoice.invoice_no}",
        body="Please view your invoice online.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.client.email],
    )

    # ✅ HTML email only
    email.attach_alternative(html_body, "text/html")

    # ❌ NO ATTACHMENT
    # email.attach_file(invoice.pdf_file.path)

    email.send()


@shared_task
def send_purchase_order_email(po_id):
    po = PurchaseOrder.objects.select_related(
        "vendor",
        "created_by"
    ).prefetch_related(
        "items__quote_item__product_service"
    ).get(pk=po_id)

    po_link = f"{settings.FRONTEND_BASE_URL}/purchase-orders/{po.id}/"

    html_body = render_to_string(
        "emails/purchase_order_email.html",
        {
            "po": po,
            "po_link": po_link,
            "sender_name": "Accounts Team",
        },
    )

    email = EmailMultiAlternatives(
        subject=f"Purchase Order {po.po_no}",
        body="Please view your purchase order online.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[po.vendor.email],
    )

    # ✅ HTML email only (same as invoice)
    email.attach_alternative(html_body, "text/html")

    # ❌ NO ATTACHMENT (same as invoice)
    email.send()
