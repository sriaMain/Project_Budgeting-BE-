

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

from reportlab.platypus import (
SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
class InvoiceService:


    @staticmethod
    def generate_invoice_number():
        today = timezone.now()
        prefix = f"INV-{today.strftime('%Y%m')}"
        last = Invoice.objects.filter(
            invoice_no__startswith=prefix
        ).order_by('-invoice_no').first()

        next_no = int(last.invoice_no.split('-')[-1]) + 1 if last else 1
        return f"{prefix}-{next_no:04d}"

    @staticmethod
    @transaction.atomic
    def create_invoice_from_quote(
        quote,
        user,
        due_days,
        product_service_id=None,
        notes="",
        terms_conditions=""
    ):
        if quote.status != "Confirmed":
            raise ValidationError("Quote must be Confirmed")

        # 🔒 Prevent duplicate invoice for SAME product group
        if product_service_id:
            if InvoiceItem.objects.filter(
                invoice__quote=quote,
                product_service_id=product_service_id
            ).exists():
                raise ValidationError(
                    "Invoice already exists for this product group."
                )

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

        # 🔥 FILTER ITEMS
        quote_items = quote.items.all()

        if product_service_id:
            quote_items = quote_items.filter(
                product_service_id=product_service_id
            )

            if not quote_items.exists():
                raise ValidationError(
                    "No quote items found for selected product group."
                )

        # 🔥 CREATE INVOICE ITEMS
        for item in quote_items:
            InvoiceItem.objects.create(
                invoice=invoice,
                product_service=item.product_service,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                price_per_unit=item.price_per_unit,
            )

        invoice.update_status()
        return invoice

    

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

import os
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import mm
from django.conf import settings


class InvoicePDFService:

    @staticmethod
    def generate(invoice):
        pdf_dir = os.path.join(settings.MEDIA_ROOT, "invoices")
        os.makedirs(pdf_dir, exist_ok=True)

        file_name = f"Invoice_{invoice.invoice_no}.pdf"
        file_path = os.path.join(pdf_dir, file_name)

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm,
        )

        styles = getSampleStyleSheet()
        elements = []

        # -------------------------------
        # 🔵 HEADER BAR (BLUE)
        # -------------------------------
        header_table = Table(
            [[
                Paragraph(
                    "<font size=20 color='white'><b>INV-</b></font>",
                    styles["Normal"]
                ),
                Paragraph(
                    "<font color='white'>"
                    "<b>SRIA INFOTECH PRIVATE LTD</b><br/>"
                    "1ST FLOOR, 1-121/S3, SURVEY NO 63 PART<br/>"
                    "BEHIND HOTEL SITARA GRAND MIYAPUR<br/>"
                    "Hyderabad, Telangana, India, 500049"
                    "</font>",
                    styles["Normal"]
                ),
            ]],
            colWidths=[60*mm, 120*mm],
        )

        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#3f8edb")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ]))

        elements.append(header_table)
        elements.append(Spacer(1, 16))

        # -------------------------------
        # 🧾 BILLED TO + DETAILS
        # -------------------------------
        elements.append(
            Paragraph(
                f"<b>Billed To:</b><br/>{invoice.client.company_name}",
                styles["Normal"]
            )
        )
        elements.append(Spacer(1, 10))

        elements.append(
            Paragraph(
                f"<b>Invoice Date:</b> {invoice.issue_date}<br/>"
                f"<b>Due Date:</b> {invoice.due_date}<br/>"
                f"<b>GSTIN:</b> 36ABICS3346M1ZV",
                styles["Normal"]
            )
        )
        elements.append(Spacer(1, 18))

        # -------------------------------
        # 📊 ITEMS TABLE
        # -------------------------------
        table_data = [
            ["Quantity", "Unit", "Unit Price", "Taxes", "Amount"]
        ]

        for item in invoice.items.all():
            table_data.append([
                f"{item.quantity}",
                item.unit,
                f"{item.price_per_unit}",
                "SGST 9%, CGST 9%",
                f"{item.amount}",
            ])

        items_table = Table(
            table_data,
            colWidths=[30*mm, 30*mm, 35*mm, 45*mm, 35*mm],
        )

        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf2fb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0b5ed7")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ALIGN", (0, 1), (-1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ]))

        elements.append(items_table)
        elements.append(Spacer(1, 18))

        # -------------------------------
        # 💰 SUMMARY SECTION (LEFT + RIGHT)
        # -------------------------------
        summary_table = Table(
            [
                ["Subtotal", f"{invoice.sub_total}", "Total", f"{invoice.total_amount}"],
                ["Tax (%)", f"{invoice.tax_percentage}", "In-house", "—"],
                ["Total (INR)", f"{invoice.total_amount}", "Out-Sourced", "—"],
                ["Invoiced Sum (INR)", "—", "To be Invoiced (INR)", "—"],
            ],
            colWidths=[50*mm, 40*mm, 50*mm, 40*mm],
        )

        summary_table.setStyle(TableStyle([
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 18))

        # -------------------------------
        # 📜 TERMS & FOOTER
        # -------------------------------
        elements.append(
            Paragraph(
                "<b>Payment terms:</b> Immediate Payment<br/>"
                f"<b>Payment Communication:</b> INV-{invoice.invoice_no}<br/>"
                "<b>Terms & Conditions:</b> https://www.sriainfotech.com/",
                styles["Normal"]
            )
        )

        elements.append(Spacer(1, 20))

        elements.append(
            Paragraph(
                "hr@sriainfotech.com | www.sriainfotech.com | Page 1 / 1",
                ParagraphStyle(
                    "footer",
                    fontSize=9,
                    textColor=colors.grey,
                    alignment=1,
                ),
            )
        )

        doc.build(elements)

        invoice.pdf_file.name = f"invoices/{file_name}"
        invoice.save(update_fields=["pdf_file"])

        return file_path
