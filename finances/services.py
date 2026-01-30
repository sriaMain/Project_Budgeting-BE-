

from django.db import transaction
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from decimal import Decimal
from datetime import timedelta
import os
import logging

logger = logging.getLogger(__name__)

from .models import Invoice, InvoiceItem ,InvoicePayment

from reportlab.platypus import (
SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from django.db.models import Sum

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
        product_service_ids=None,
        product_group_ids=None,
        quote_item_ids=None,
        invoice_items=None,
        notes="",
        terms_conditions=""
    ):
        if quote.status != "Confirmed":
            raise ValidationError("Quote must be Confirmed")

        quote_items = quote.items.all()
        invoice_items = invoice_items or []

        if invoice_items and not isinstance(invoice_items, (list, tuple)):
            raise ValidationError("invoice_items must be a list of {quote_item_id, quantity}")

        override_quantities = {
            int(item["quote_item_id"]): Decimal(str(item["quantity"]))
            for item in invoice_items
        }

        if invoice_items and not override_quantities:
            raise ValidationError("invoice_items provided but no valid overrides were found")

        selected_quote_item_ids = quote_item_ids or []
        if override_quantities:
            selected_quote_item_ids = list(override_quantities.keys())

        logger.info(f"Starting with {quote_items.count()} total quote items")
        logger.info(
            "Filters: product_service_id=%s, product_service_ids=%s, "
            "product_group_ids=%s, quote_item_ids=%s, invoice_items=%s",
            product_service_id,
            product_service_ids,
            product_group_ids,
            quote_item_ids,
            invoice_items,
        )

        # 🔥 FILTERING - only one filter should be applied
        if selected_quote_item_ids:
            quote_items = quote_items.filter(id__in=selected_quote_item_ids)
            logger.info(
                "Filtered by quote_item_ids=%s, items count: %s",
                selected_quote_item_ids,
                quote_items.count(),
            )

        elif product_service_id:
            quote_items = quote_items.filter(
                product_service_id=product_service_id
            )
            logger.info(f"Filtered by product_service_id={product_service_id}, items count: {quote_items.count()}")

        elif product_service_ids and len(product_service_ids) > 0:
            quote_items = quote_items.filter(
                product_service_id__in=product_service_ids
            )
            logger.info(f"Filtered by product_service_ids={product_service_ids}, items count: {quote_items.count()}")

        elif product_group_ids and len(product_group_ids) > 0:
            from product_group.models import Product_Services

            service_ids = list(Product_Services.objects.filter(
                product_group_id__in=product_group_ids
            ).values_list('id', flat=True))

            logger.info(f"product_group_ids={product_group_ids} resolved to service_ids={service_ids}")

            quote_items = quote_items.filter(
                product_service_id__in=service_ids
            )
            logger.info(f"Filtered by product_group_ids={product_group_ids}, items count: {quote_items.count()}")
        
        else:
            logger.info("No filter applied - returning all quote items")

        if not quote_items.exists():
            raise ValidationError("No quote items found for selected filter.")

        if override_quantities and quote_items.count() != len(override_quantities):
            missing_ids = set(override_quantities.keys()) - set(quote_items.values_list("id", flat=True))
            raise ValidationError(
                f"invoice_items refer to quote items not found on this quote: {sorted(missing_ids)}"
            )

        # 🔒 Partial invoicing support: compute remaining quantity per selected quote item
        # Sum of already invoiced quantities per product_service for this quote
        invoiced_by_service = (
            InvoiceItem.objects
            .filter(invoice__quote=quote)
            .values('product_service_id')
            .annotate(total_qty=Sum('quantity'))
        )
        invoiced_map = {row['product_service_id']: row['total_qty'] or Decimal('0') for row in invoiced_by_service}

        # 🔥 Create Invoice
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

        # 🔥 Create Invoice Items (respecting any per-invoice quantity overrides and remaining quantities)
        created_count = 0
        errors = []
        for item in quote_items:
            service_id = item.product_service_id
            already_invoiced_qty = invoiced_map.get(service_id, Decimal('0'))

            # Remaining = quote item's quantity - sum of invoiced quantities for this service in this quote
            remaining = Decimal(str(item.quantity)) - already_invoiced_qty
            if remaining <= Decimal('0'):
                errors.append(f"{item.product_service.product_service_name} has no remaining quantity to invoice")
                continue

            # If an override is provided, use it; otherwise invoice remaining
            requested = override_quantities.get(item.id, None)
            if requested is None:
                quantity = remaining
            else:
                if Decimal(str(requested)) > remaining:
                    errors.append(
                        f"Requested quantity {requested} exceeds remaining {remaining} for {item.product_service.product_service_name}"
                    )
                    continue
                quantity = Decimal(str(requested))

            InvoiceItem.objects.create(
                invoice=invoice,
                product_service=item.product_service,
                description=item.description,
                quantity=quantity,
                unit=item.unit,
                price_per_unit=item.price_per_unit,
            )
            created_count += 1

        if created_count == 0:
            raise ValidationError(errors[0] if errors else "No invoice items could be created for the requested selection")

        invoice.update_status()
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

from .models import PurchaseOrder
class PurchaseOrderService:

    @staticmethod
    def generate_po_number():
        from datetime import datetime
        count = PurchaseOrder.objects.count() + 1
        return f"PO-{datetime.now().strftime('%Y%m')}-{count:04d}"
