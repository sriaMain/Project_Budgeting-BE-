
# # services.py
# from django.db import transaction
# from django.core.mail import EmailMessage
# from django.template.loader import render_to_string
# from django.conf import settings
# import os
# from .models import Invoice, InvoiceItem, InvoiceMilestone, InvoicePayment
# from django.utils import timezone
# from decimal import Decimal
# from django.core.exceptions import ValidationError
# from datetime import timedelta

# class InvoiceService:
#     """
#     All invoice business logic lives here
#     """

#     @staticmethod
#     def generate_invoice_number():
#         """
#         Industry-safe, concurrent-safe invoice number generator
#         Format: INV-YYYYMM-0001
#         """
#         today = timezone.now()
#         prefix = f"INV-{today.strftime('%Y%m')}"

#         with transaction.atomic():
#             last = (
#                 Invoice.objects
#                 .select_for_update()
#                 .filter(invoice_no__startswith=prefix)
#                 .order_by('-invoice_no')
#                 .first()
#             )

#             next_number = (
#                 int(last.invoice_no.split('-')[-1]) + 1
#                 if last else 1
#             )

#             return f"{prefix}-{next_number:04d}"

#     @staticmethod
#     @transaction.atomic
#     def create_invoice_from_quote(
#         quote,
#         user,
#         due_days=30,
#         include_milestones=False,
#         milestone_data=None,
#         notes="",
#         terms_conditions=""
#     ):
#         if quote.status != "Confirmed":
#             raise ValidationError("Invoice can only be generated from Confirmed quotes")

#         if Invoice.objects.filter(quote=quote).exists():
#             raise ValidationError("Invoice already exists for this quote")

#         invoice = Invoice.objects.create(
#             quote=quote,
#             client=quote.client,
#             project=getattr(quote, "project", None),
#             issue_date=timezone.now().date(),
#             due_date=timezone.now().date() + timedelta(days=due_days),
#             tax_percentage=quote.tax_percentage,
#             notes=notes,
#             terms_conditions=terms_conditions,
#             created_by=user,
#             updated_by=user,
#             status="Issued",
#         )

#         # Copy quote items
#         for item in quote.items.all():
#             InvoiceItem.objects.create(
#                 invoice=invoice,
#                 product_service=item.product_service,
#                 description=item.description,
#                 quantity=item.quantity,
#                 unit=item.unit,
#                 price_per_unit=item.price_per_unit,
#             )

#         invoice.calculate_totals()
#         invoice.save()

#         return invoice

    
#     @staticmethod
#     def create_milestones(invoice, milestone_data):
#         """
#         Create payment milestones for invoice
        
#         milestone_data format:
#         [
#             {
#                 'title': 'Initial Payment',
#                 'percentage': 30,
#                 'due_date': date_object,
#                 'description': 'First milestone'
#             },
#             ...
#         ]
#         """
#         total_percentage = sum(m['percentage'] for m in milestone_data)
#         if total_percentage != 100:
#             raise ValidationError("Milestone percentages must sum to 100%")
        
#         for idx, milestone in enumerate(milestone_data, 1):
#             amount = (invoice.total_amount * Decimal(milestone['percentage'])) / 100
            
#             InvoiceMilestone.objects.create(
#                 invoice=invoice,
#                 milestone_no=idx,
#                 title=milestone['title'],
#                 description=milestone.get('description', ''),
#                 due_date=milestone['due_date'],
#                 amount=amount,
#                 percentage=milestone['percentage']
#             )
    
#     @staticmethod
#     @transaction.atomic
#     def record_payment(invoice, amount, payment_date, payment_method, reference_no, 
#                       milestone=None, notes='', user=None, attachment=None):
#         """Record a payment against an invoice"""
        
#         # Validate amount
#         invoice.calculate_totals()
#         if amount > invoice.balance_amount:
#             raise ValidationError(f"Payment amount exceeds invoice balance of {invoice.balance_amount}")
        
#         # Create payment record
#         payment = InvoicePayment.objects.create(
#             invoice=invoice,
#             milestone=milestone,
#             payment_date=payment_date,
#             amount=amount,
#             payment_method=payment_method,
#             reference_no=reference_no,
#             notes=notes,
#             attachment=attachment,
#             created_by=user
#         )
        
#         return payment
    
#     @staticmethod
#     def generate_pdf(invoice):
#         """Generate PDF for invoice"""
#         from weasyprint import HTML
        
#         html_string = render_to_string('invoices/invoice_pdf.html', {
#             'invoice': invoice,
#             'company': settings.COMPANY_INFO,  # Your company details
#         })
        
#         html = HTML(string=html_string)
#         pdf_file = f'invoice_{invoice.invoice_no}.pdf'
#         pdf_path = os.path.join(settings.MEDIA_ROOT, 'invoices/pdfs/', pdf_file)
        
#         os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
#         html.write_pdf(pdf_path)
        
#         invoice.pdf_file = f'invoices/pdfs/{pdf_file}'
#         invoice.save()
        
#         return pdf_path
    
#     @staticmethod
#     def send_invoice_email(invoice, recipient_emails, subject=None, message=''):
#         """Send invoice via email"""
        
#         if not subject:
#             subject = f'Invoice {invoice.invoice_no} from {settings.COMPANY_NAME}'
        
#         email_body = render_to_string('invoices/invoice_email.html', {
#             'invoice': invoice,
#             'message': message,
#         })
        
#         email = EmailMessage(
#             subject=subject,
#             body=email_body,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             to=recipient_emails,
#         )
        
#         email.content_subtype = 'html'
        
#         # Attach PDF if exists
#         if invoice.pdf_file:
#             email.attach_file(invoice.pdf_file.path)
        
#         email.send()
        
#         invoice.sent_date = timezone.now()
#         invoice.save()
        
#         return True
    
#     @staticmethod
#     def cancel_invoice(invoice, reason='', user=None):
#         """Cancel an invoice"""
        
#         if invoice.paid_amount > 0:
#             raise ValidationError("Cannot cancel invoice with payments. Please refund payments first.")
        
#         invoice.status = 'Cancelled'
#         invoice.notes += f"\n\nCancelled by {user.get_full_name() if user else 'System'} on {timezone.now()}\nReason: {reason}"
#         invoice.updated_by = user
#         invoice.save()
        
#         return invoice.



from django.db import transaction
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from decimal import Decimal
from datetime import timedelta
import os

from .models import Invoice, InvoiceItem ,InvoicePayment


class InvoiceService:

    @staticmethod
    def generate_invoice_number():
        today = timezone.now()
        prefix = f"INV-{today.strftime('%Y%m')}"
        last = Invoice.objects.filter(invoice_no__startswith=prefix).order_by('-invoice_no').first()
        next_no = int(last.invoice_no.split('-')[-1]) + 1 if last else 1
        return f"{prefix}-{next_no:04d}"

    @staticmethod
    @transaction.atomic
    def create_invoice_from_quote(quote, user, due_days, notes="", terms_conditions=""):
        if quote.status != "Confirmed":
            raise ValidationError("Quote must be Confirmed")

        if Invoice.objects.filter(quote=quote).exists():
            raise ValidationError("Invoice already exists")

        invoice = Invoice.objects.create(
            invoice_no=InvoiceService.generate_invoice_number(),
            quote=quote,
            client=quote.client,
            project=getattr(quote, 'project', None),
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=due_days),
            tax_percentage=quote.tax_percentage,
            notes=notes,
            terms_conditions=terms_conditions,
            created_by=user,
            updated_by=user
        )

        for item in quote.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                product_service=item.product_service,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                price_per_unit=item.price_per_unit
            )

        invoice.update_status()
        return invoice

   
    
    # @staticmethod
    # @transaction.atomic
    # def record_payment(
    #     invoice,
    #     amount,
    #     payment_date,
    #     payment_method,
    #     reference_no,
    #     notes="",
    #     user=None,
    #     attachment=None
    # ):
    #     invoice.calculate_totals()

    #     if amount > invoice.balance_amount:
    #         raise ValidationError(
    #             f"Payment exceeds invoice balance {invoice.balance_amount}"
    #         )

    #     payment = InvoicePayment.objects.create(
    #         invoice=invoice,
    #         milestone=milestone,
    #         payment_date=payment_date,
    #         amount=amount,
    #         payment_method=payment_method,
    #         reference_no=reference_no,
    #         notes=notes,
    #         attachment=attachment,
    #         created_by=user,
    #     )

    #     return payment

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    @staticmethod
    def generate_pdf(invoice):
        from weasyprint import HTML

        html_string = render_to_string(
            "invoices/invoice_pdf.html",
            {
                "invoice": invoice,
                "company": settings.COMPANY_INFO,
            }
        )

        pdf_name = f"invoice_{invoice.invoice_no}.pdf"
        pdf_path = os.path.join(
            settings.MEDIA_ROOT,
            "invoices/pdfs",
            pdf_name
        )

        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        HTML(string=html_string).write_pdf(pdf_path)

        invoice.pdf_file = f"invoices/pdfs/{pdf_name}"
        invoice.save(update_fields=["pdf_file"])

        return pdf_path

    # ------------------------------------------------------------------
    # EMAIL
    # ------------------------------------------------------------------
    @staticmethod
    def send_invoice_email(invoice, recipient_emails, subject=None, message=""):
        subject = subject or f"Invoice {invoice.invoice_no}"

        body = render_to_string(
            "invoices/invoice_email.html",
            {"invoice": invoice, "message": message}
        )

        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_emails,
        )

        email.content_subtype = "html"

        if invoice.pdf_file:
            email.attach_file(invoice.pdf_file.path)

        email.send()

        invoice.sent_date = timezone.now()
        invoice.save(update_fields=["sent_date"])

        return True

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------
    @staticmethod
    def cancel_invoice(invoice, reason="", user=None):
        if invoice.paid_amount > Decimal("0.00"):
            raise ValidationError(
                "Cannot cancel invoice with payments"
            )

        invoice.status = "Cancelled"
        invoice.notes += (
            f"\n\nCancelled by "
            f"{user.get_full_name() if user else 'System'} "
            f"on {timezone.now()}\nReason: {reason}"
        )
        invoice.updated_by = user
        invoice.save(update_fields=["status", "notes", "updated_by"])

        return invoice
