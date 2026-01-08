# views.py (APIView Implementation)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import FileResponse, HttpResponse
from io import BytesIO
from datetime import timedelta, datetime
from decimal import Decimal

from .models import Invoice, InvoiceItem, InvoicePayment, PurchaseOrder, Vendor, VendorBill
from .serializers import (
    InvoiceListSerializer, InvoiceDetailSerializer, InvoiceItemSerializer,
    InvoicePaymentSerializer,
    GenerateInvoiceSerializer, RecordPaymentSerializer,
    SendInvoiceEmailSerializer, CancelInvoiceSerializer, InvoiceStatsSerializer, PurchaseOrderSerializer,VendorBillSerializer,OutgoingPaymentSerializer   
)
from .services import InvoiceService
from django.core.exceptions import ValidationError
from product_group.models import Quote
from django.http import Http404
from django.conf import settings
from .tasks import send_invoice_email
from .utils import validate_invoice_token
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from Project.models import Project

class QuotationDetailView(APIView):
    """
    Get quotation details with invoice generation capability
    
    GET /api/quotations/<quote_id>/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, pk):
        from product_group.models import Quote
        from product_group.serializers import QuoteDetailSerializer
        
        quote = get_object_or_404(Quote, pk=pk)
        
        # Check if invoice already exists
        existing_invoice = Invoice.objects.filter(quote=quote).first()
        
        quote_serializer = QuoteDetailSerializer(quote)
        
        response_data = {
            'quote': quote_serializer.data,
            'can_generate_invoice': quote.status == 'Confirmed' and not existing_invoice,
            'existing_invoice': None
        }
        
        if existing_invoice:
            invoice_serializer = InvoiceListSerializer(existing_invoice)
            response_data['existing_invoice'] = invoice_serializer.data
        
        return Response(response_data, status=status.HTTP_200_OK)


class InvoiceListView(APIView):
    """
    List all invoices with filters and pagination
    
    GET /api/invoices/
    Query Params:
        - status: filter by status
        - client_id: filter by client
        - date_from: filter from date
        - date_to: filter to date
        - search: search in invoice_no or client name
        - page: page number
        - page_size: items per page (default 20)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        # Base queryset
        queryset = Invoice.objects.select_related(
            'client', 'quote', 'project', 'created_by'
        ).prefetch_related('items', 'payments')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        client_id = request.query_params.get('client_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        search = request.query_params.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        if date_from:
            queryset = queryset.filter(issue_date__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(issue_date__lte=date_to)
        
        if search:
            queryset = queryset.filter(
                Q(invoice_no__icontains=search) |
                Q(client__name__icontains=search)
            )
        
        # Update overdue invoices
        overdue_invoices = queryset.filter(
            status='Issued',
            due_date__lt=timezone.now().date()
        )
        for invoice in overdue_invoices:
            invoice.update_status()
        
        # Order by created date
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        invoices = queryset[start:end]
        
        serializer = InvoiceListSerializer(invoices, many=True)
        
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class InvoiceDetailView(APIView):
    
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    
    def get(self, request, invoice_id):
        invoice = get_object_or_404(
            Invoice.objects.select_related('client', 'quote', 'project')
            .prefetch_related('items', 'payments'),
            id=invoice_id
        )
        
        # Calculate and update totals
        invoice.calculate_totals()
        invoice.save()
        
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        serializer = InvoiceDetailSerializer(invoice, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
  
    def delete(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)

        # ✅ BLOCK DELETE IF PAYMENTS EXIST
        if invoice.payments.exists():
            return Response(
                {
                    "error": "Invoice has payments and cannot be deleted"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ DELETE PDF FILE IF EXISTS
        if invoice.pdf_file:
            invoice.pdf_file.delete(save=False)

        # ✅ DELETE INVOICE
        invoice.delete()

        return Response(
            {"message": "Invoice deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )
        

# class GenerateInvoiceView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]

#     @transaction.atomic
#     def post(self, request):
#         serializer = GenerateInvoiceSerializer(data=request.data)

#         if not serializer.is_valid():
#             return Response(
#                 serializer.errors,
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         quote = get_object_or_404(
#             Quote,
#             pk=serializer.validated_data["quote_id"]
#         )

#         try:
#             invoice = InvoiceService.create_invoice_from_quote(
#                 quote=quote,
#                 user=request.user,
#                 due_days=serializer.validated_data["due_days"],
#                 product_service_id=serializer.validated_data.get("product_service_id"),
#                 product_service_ids=serializer.validated_data.get("product_service_ids"),
#                 product_group_id=serializer.validated_data.get("product_group_id"),
#                 notes=serializer.validated_data.get("notes", ""),
#                 terms_conditions=serializer.validated_data.get(
#                     "terms_conditions", ""
#                 ),
#             )

#         except ValidationError as e:
#             return Response(
#                 {"error": str(e)},
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         response_serializer = InvoiceDetailSerializer(invoice)

#         return Response(
#             {
#                 "message": f"Invoice {invoice.invoice_no} generated successfully",
#                 "invoice": response_serializer.data,
#             },
#             status=status.HTTP_201_CREATED
#         )
class GenerateInvoiceView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        serializer = GenerateInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        quote = get_object_or_404(
            Quote,
            pk=serializer.validated_data["quote_id"]
        )

        # 🔥 Normalize product_group_id → product_group_ids (list)
        product_group_ids = serializer.validated_data.get("product_group_ids") or []
        
        if serializer.validated_data.get("product_group_id"):
            product_group_ids = [serializer.validated_data["product_group_id"]]

        # Get other filters
        product_service_id = serializer.validated_data.get("product_service_id")
        product_service_ids = serializer.validated_data.get("product_service_ids") or []
        quote_item_ids = serializer.validated_data.get("quote_item_ids") or []

        try:
            invoice = InvoiceService.create_invoice_from_quote(
                quote=quote,
                user=request.user,
                due_days=serializer.validated_data["due_days"],
                product_service_id=product_service_id,
                product_service_ids=product_service_ids,
                product_group_ids=product_group_ids,
                quote_item_ids=quote_item_ids,
                notes=serializer.validated_data.get("notes", ""),
                terms_conditions=serializer.validated_data.get("terms_conditions", ""),
            )

        except ValidationError as e:
            return Response(
                {"error": e.messages[0] if hasattr(e, "messages") else str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": f"Invoice {invoice.invoice_no} generated successfully",
                "invoice": InvoiceDetailSerializer(invoice).data,
            },
            status=status.HTTP_201_CREATED
        )



class RecordPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)

        serializer = InvoicePaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            payment = InvoicePayment.objects.create(
                invoice=invoice,
                created_by=request.user,
                **serializer.validated_data
            )
        except ValidationError as e:
            return Response(
                {"error": e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "message": "Payment recorded successfully",
                "payment": InvoicePaymentSerializer(payment).data
            },
            status=status.HTTP_201_CREATED
        )

# class RecordPaymentView(APIView):
#     """
#     Record a payment for an invoice
    
#     POST /api/invoices/<invoice_id>/payment/
#     {
#         "amount": 5000.00,
#         "payment_date": "2024-01-15",
#         "payment_method": "Bank Transfer",
#         "reference_no": "TXN123456",
#         "milestone_id": 1,
#         "notes": "Payment received",
#         "attachment": <file>
#     }
#     """
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]
#     parser_classes = [MultiPartParser, FormParser, JSONParser]
    
#     @transaction.atomic
#     def post(self, request, invoice_id):
#         invoice = get_object_or_404(Invoice, id=invoice_id)
        
#         # Add invoice_id to data
#         data = request.data.copy()
#         data['invoice_id'] = invoice_id
        
#         serializer = RecordPaymentSerializer(data=data)
        
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Get milestone if provided
#             milestone = None
#             if serializer.validated_data.get('milestone_id'):
#                 milestone = get_object_or_404(
#                     Invoice,
#                     id=serializer.validated_data['milestone_id'],
#                     invoice=invoice
#                 )
            
#             # Record payment
#             payment = InvoiceService.record_payment(
#                 invoice=invoice,
#                 amount=serializer.validated_data['amount'],
#                 payment_date=serializer.validated_data['payment_date'],
#                 payment_method=serializer.validated_data['payment_method'],
#                 reference_no=serializer.validated_data.get('reference_no', ''),
#                 # milestone=milestone,
#                 notes=serializer.validated_data.get('notes', ''),
#                 user=request.user,
#                 attachment=serializer.validated_data.get('attachment')
#             )
            
#             response_serializer = InvoicePaymentSerializer(payment)
#             return Response(
#                 {
#                     'message': f'Payment of {payment.amount} recorded successfully',
#                     'payment': response_serializer.data
#                 },
#                 status=status.HTTP_201_CREATED
#             )
        
#         except Exception as e:
#             return Response(
#                 {'error': str(e)},
#                 status=status.HTTP_400_BAD_REQUEST
#             )


class InvoicePaymentListView(APIView):
    """
    Get all payments for an invoice
    
    GET /api/invoices/<invoice_id>/payments/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        payments = invoice.payments.all().order_by('-payment_date')
        
        serializer = InvoicePaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DownloadInvoicePDFView(APIView):
    """
    Generate and download invoice PDF
    
    GET /api/invoices/<invoice_id>/pdf/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        try:
            pdf_path = InvoiceService.generate_pdf(invoice)
            
            response = FileResponse(
                open(pdf_path, 'rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="Invoice_{invoice.invoice_no}.pdf"'
            
            return response
        
        except Exception as e:
            return Response(
                {'error': f'Error generating PDF: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class SendInvoiceEmailView(APIView):
#     """
#     Send invoice via email
    
#     POST /api/invoices/<invoice_id>/send-email/
#     {
#         "recipient_emails": ["client@example.com", "finance@example.com"],
#         "subject": "Invoice #INV-001",
#         "message": "Please find attached invoice...",
#         "include_pdf": true
#     }
#     """
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]
    
#     def post(self, request, invoice_id):
#         invoice = get_object_or_404(Invoice, id=invoice_id)
        
#         serializer = SendInvoiceEmailSerializer(data=request.data)
        
#         if not serializer.is_valid():
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
#         try:
#             # Generate PDF if not exists and include_pdf is True
#             if serializer.validated_data.get('include_pdf', True) and not invoice.pdf_file:
#                 InvoiceService.generate_pdf(invoice)
            
#             # Send email
#             InvoiceService.send_invoice_email(
#                 invoice=invoice,
#                 recipient_emails=serializer.validated_data['recipient_emails'],
#                 subject=serializer.validated_data.get('subject', ''),
#                 message=serializer.validated_data.get('message', '')
#             )
            
#             return Response(
#                 {
#                     'message': f'Invoice sent successfully to {", ".join(serializer.validated_data["recipient_emails"])}'
#                 },
#                 status=status.HTTP_200_OK
#             )
        
#         except Exception as e:
#             return Response(
#                 {'error': f'Error sending email: {str(e)}'},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )


class CancelInvoiceView(APIView):
    """
    Cancel an invoice
    
    POST /api/invoices/<invoice_id>/cancel/
    {
        "reason": "Client cancelled the project"
    }
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    @transaction.atomic
    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        serializer = CancelInvoiceSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            InvoiceService.cancel_invoice(
                invoice,
                serializer.validated_data['reason'],
                request.user
            )
            
            response_serializer = InvoiceDetailSerializer(invoice)
            return Response(
                {
                    'message': f'Invoice {invoice.invoice_no} cancelled successfully',
                    'invoice': response_serializer.data
                },
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class InvoiceShareableLinkView(APIView):
    """
    Generate shareable link for invoice
    
    GET /api/invoices/<invoice_id>/share/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        import hashlib
        from django.conf import settings
        
        token = hashlib.sha256(
            f"{invoice.id}{invoice.invoice_no}{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]
        
        link = request.build_absolute_uri(
            f'/api/invoices/view/{invoice.id}/{token}/'
        )
        
        return Response({
            'shareable_link': link,
            'invoice_no': invoice.invoice_no,
            'token': token
        }, status=status.HTTP_200_OK)


class PublicInvoiceView(APIView):
    """
    Public view of invoice (no authentication required)
    
    GET /api/invoices/view/<invoice_id>/<token>/
    """
    permission_classes = []
    
    def get(self, request, invoice_id, token):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        
        # Verify token
        import hashlib
        from django.conf import settings
        
        expected_token = hashlib.sha256(
            f"{invoice.id}{invoice.invoice_no}{settings.SECRET_KEY}".encode()
        ).hexdigest()[:16]
        
        if token != expected_token:
            return Response(
                {'error': 'Invalid or expired link'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = InvoiceDetailSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceStatisticsView(APIView):
    """
    Get invoice statistics and analytics
    
    GET /api/invoices/statistics/
    Query Params:
        - date_from: filter from date
        - date_to: filter to date
        - client_id: filter by client
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        # Base queryset
        invoices = Invoice.objects.all()
        
        # Apply filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        client_id = request.query_params.get('client_id')
        
        if date_from:
            invoices = invoices.filter(issue_date__gte=date_from)
        
        if date_to:
            invoices = invoices.filter(issue_date__lte=date_to)
        
        if client_id:
            invoices = invoices.filter(client_id=client_id)
        
        # Calculate stats
        total_invoices = invoices.count()
        
        aggregates = invoices.aggregate(
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            pending_amount=Sum('balance_amount')
        )
        
        overdue_amount = invoices.filter(
            status='Overdue'
        ).aggregate(Sum('balance_amount'))['balance_amount__sum'] or Decimal('0')
        
        # Status breakdown
        status_breakdown = {}
        for choice in Invoice.STATUS_CHOICES:
            count = invoices.filter(status=choice[0]).count()
            status_breakdown[choice[0]] = {
                'count': count,
                'label': choice[1]
            }
        
        # Payment method breakdown
        payments = InvoicePayment.objects.filter(
            invoice__in=invoices
        ).values('payment_method').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        payment_method_breakdown = {
            p['payment_method']: {
                'total': float(p['total']),
                'count': p['count']
            }
            for p in payments
        }
        
        # Recent invoices
        recent_invoices = invoices.select_related('client').order_by('-created_at')[:5]
        
        # Upcoming due
        upcoming_due = invoices.filter(
            status__in=['Issued', 'Partially Paid'],
            due_date__gte=timezone.now().date(),
            due_date__lte=timezone.now().date() + timedelta(days=7)
        ).select_related('client').order_by('due_date')[:5]
        
        stats_data = {
            'total_invoices': total_invoices,
            'total_amount': aggregates['total_amount'] or Decimal('0'),
            'paid_amount': aggregates['paid_amount'] or Decimal('0'),
            'pending_amount': aggregates['pending_amount'] or Decimal('0'),
            'overdue_amount': overdue_amount,
            'status_breakdown': status_breakdown,
            'payment_method_breakdown': payment_method_breakdown,
            'recent_invoices': InvoiceListSerializer(recent_invoices, many=True).data,
            'upcoming_due': InvoiceListSerializer(upcoming_due, many=True).data,
        }
        
        serializer = InvoiceStatsSerializer(stats_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SendInvoiceEmailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)

        if not invoice.client.email:
            return Response(
                {"error": "Client email not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        send_invoice_email.delay(invoice.id)

        return Response(
            {"message": "Invoice email sent successfully"},
            status=status.HTTP_200_OK
        )



from django.shortcuts import get_object_or_404
from .services import InvoicePDFService

class DownloadInvoicePDFView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)

        # 🔥 FORCE REGENERATE PDF EVERY TIME
        pdf_path = InvoicePDFService.generate(invoice)

        return FileResponse(
            open(pdf_path, "rb"),
            content_type="application/pdf",
            as_attachment=True,
            filename=f"Invoice_{invoice.invoice_no}.pdf"
        )

from django.template.loader import render_to_string

class PublicInvoicePDFView(APIView):
    permission_classes = []  # 🔓 Public access

    def get(self, request, token):

        # 🔒 STEP 5.1 — token is validated
        try:
            data = validate_invoice_token(token)
            invoice_id = data["invoice_id"]
        except Exception:
            raise Http404("Invalid or expired link")

        # 📦 STEP 5.2 — invoice fetched
        invoice = Invoice.objects.get(pk=invoice_id)

        # 🧾 STEP 5.3 — HTML rendered
        html = render_to_string(
            "quote_invoice.html",
            {"invoice": invoice}
        )

        # 📄 STEP 5.4 — PDF generated
        pdf_buffer = BytesIO()
        pisa.CreatePDF(html, pdf_buffer)

        # 🌐 STEP 5.5 — PDF opened in browser
        return HttpResponse(
            pdf_buffer.getvalue(),
            content_type="application/pdf",
            headers={
                "Content-Disposition":
                f'inline; filename="Invoice_{invoice.invoice_no}.pdf"'
            }
        )


from .utils import generate_invoice_token
class ShareInvoiceLinkView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    """
    Called when user clicks 'Share via link'
    """

    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, pk=invoice_id)

        # 🔑 STEP 3.1 — token is generated HERE
        token = generate_invoice_token(invoice.id)

        # 🔗 STEP 3.2 — token is placed inside URL
        public_link = (
            f"{settings.FRONTEND_BASE_URL}/public/invoice/{token}/"
        )

        # 🔁 STEP 3.3 — link is returned
        return Response({
            "public_invoice_link": public_link
        })


# ============================================================================
# PURCHASE ORDER VIEWS
# ============================================================================

class PurchaseOrderListView(APIView):
    """
    List all purchase orders with filters
    
    GET /api/purchase-orders/
    Query Params:
        - status: filter by status (draft, issued, completed, cancelled)
        - vendor_id: filter by vendor
        - page: page number
        - page_size: items per page
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        from .models import PurchaseOrder
        
        queryset = PurchaseOrder.objects.select_related(
            'vendor', 'quote', 'project', 'created_by'
        ).prefetch_related('items')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        vendor_id = request.query_params.get('vendor_id')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if vendor_id:
            queryset = queryset.filter(vendor_id=vendor_id)
        
        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = queryset.count()
        purchase_orders = queryset.order_by('-issue_date')[start:end]
        
        from .serializers import PurchaseOrderSerializer
        serializer = PurchaseOrderSerializer(purchase_orders, many=True)
        
        return Response({
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size,
            'results': serializer.data
        }, status=status.HTTP_200_OK)


class PurchaseOrderDetailView(APIView):
    """
    Get, update, or delete a purchase order
    
    GET /api/purchase-orders/<po_id>/
    PUT /api/purchase-orders/<po_id>/
    DELETE /api/purchase-orders/<po_id>/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request, po_id):
        from .models import PurchaseOrder
        from .serializers import PurchaseOrderSerializer
        
        po = get_object_or_404(PurchaseOrder, id=po_id)
        serializer = PurchaseOrderSerializer(po)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, po_id):
        from .models import PurchaseOrder
        from .serializers import PurchaseOrderSerializer
        
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        if po.status != 'draft':
            return Response(
                {"error": "Only draft POs can be edited"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = PurchaseOrderSerializer(po, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, po_id):
        from .models import PurchaseOrder
        
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        if po.status != 'draft':
            return Response(
                {"error": "Only draft POs can be deleted"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        po.delete()
        return Response(
            {"message": "Purchase order deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )


class CreatePurchaseOrderView(APIView):
    """
    Create a new purchase order from a quote
    
    POST /api/purchase-orders/create/
    {
        "quote_id": 47,
        "vendor_id": 2,
        "project_id": 22,
        "quote_item_ids": [67, 68]
    }
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    @transaction.atomic
    def post(self, request):
        from .models import PurchaseOrder, PurchaseOrderItem
        from product_group.models import Quote
        
        quote_id = request.data.get('quote_id')
        vendor_id = request.data.get('vendor_id')
        project_id = request.data.get('project_id')
        quote_item_ids = request.data.get('quote_item_ids', [])
        
        if not all([quote_id, vendor_id, project_id]):
            return Response(
                {"error": "quote_id, vendor_id, and project_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quote = Quote.objects.get(quote_no=quote_id)
            vendor = Vendor.objects.get(id=vendor_id)
            project = Project.objects.get(id=project_id)
        except (Quote.DoesNotExist, Vendor.DoesNotExist, Project.DoesNotExist) as e:
            return Response(
                {"error": f"Invalid reference: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get quote items
        quote_items = quote.items.all()
        if quote_item_ids:
            quote_items = quote_items.filter(id__in=quote_item_ids)
        
        if not quote_items.exists():
            return Response(
                {"error": "No quote items found for PO"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate PO number
        from datetime import datetime
        po_no = f"PO-{datetime.now().strftime('%Y%m')}-{PurchaseOrder.objects.count() + 1:04d}"
        
        # Create PO
        po = PurchaseOrder.objects.create(
            po_no=po_no,
            vendor=vendor,
            quote=quote,
            project=project,
            status='draft',
            created_by=request.user
        )
        
        # Create PO items
        for item in quote_items:
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                quote_item=item,
                description=item.description,
                quantity=item.quantity,
                unit_rate=item.price_per_unit
            )
        
        from .serializers import PurchaseOrderSerializer
        serializer = PurchaseOrderSerializer(po)
        
        return Response(
            {
                "message": f"Purchase order {po.po_no} created successfully",
                "purchase_order": serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class VendorBillListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bills = VendorBill.objects.select_related('vendor', 'purchase_order')
        serializer = VendorBillSerializer(bills, many=True)
        return Response(serializer.data)
class CreateVendorBillView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        po = get_object_or_404(PurchaseOrder, id=request.data['purchase_order_id'])

        bill = VendorBill.objects.create(
            bill_no=request.data['bill_no'],
            vendor=po.vendor,
            purchase_order=po,
            bill_date=request.data['bill_date'],
            due_date=request.data['due_date'],
        )

        serializer = VendorBillSerializer(bill)
        return Response(
            {
                "message": "Vendor bill created",
                "bill": serializer.data
            },
            status=201
        )


class RecordOutgoingPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, bill_id):
        bill = get_object_or_404(VendorBill, id=bill_id)

        serializer = OutgoingPaymentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                vendor_bill=bill,
                vendor=bill.vendor
            )
            return Response(
                {"message": "Payment recorded successfully"},
                status=201
            )
        return Response(serializer.errors, status=400)
