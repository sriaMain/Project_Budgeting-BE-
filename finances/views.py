# views.py (APIView Implementation)
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q, Sum, Count,F
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
    SendInvoiceEmailSerializer, CancelInvoiceSerializer, InvoiceStatsSerializer, PurchaseOrderSerializer,ProjectAttachmentSerializer,ExpenseSerializer, ExpensePaymentSerializer,ProjectExpenseListSerializer
)
from .services import InvoiceService
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from product_group.models import Quote
from django.http import Http404
from django.conf import settings
from .tasks import send_invoice_email,send_purchase_order_email
from .utils import validate_invoice_token
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from Project.models import Project
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from decimal import Decimal
from .models import Invoice, InvoicePayment, ProjectAttachment,Expense
from django.db.models.functions import Coalesce




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
        invoice_items = serializer.validated_data.get("invoice_items") or []

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
                invoice_items=invoice_items,
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


class ProjectPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_id):
        """
        List all payments related to a project
        """
        project = get_object_or_404(Project, id=project_id)

        payments = (
            InvoicePayment.objects
            .filter(invoice__project=project)
            .select_related('invoice', 'created_by')
            .order_by('-payment_date', '-created_at')
        )

        serializer = InvoicePaymentSerializer(payments, many=True)

        return Response({
            "project_id": project.id,
            "project_name": project.name,
            "count": payments.count(),
            "payments": serializer.data
        })

    def post(self, request, project_id):
        """
        Create a payment for a project invoice
        """
        project = get_object_or_404(Project, id=project_id)

        invoice_id = request.data.get('invoice')
        if not invoice_id:
            return Response(
                {"detail": "Invoice ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔒 Ensure invoice belongs to this project
        invoice = get_object_or_404(
            Invoice,
            id=invoice_id,
            project=project
        )

        serializer = InvoicePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = serializer.save(
            invoice=invoice,
            created_by=request.user
        )

        return Response(
            {
                "message": "Payment recorded successfully",
                "payment": InvoicePaymentSerializer(payment).data
            },
            status=status.HTTP_201_CREATED
        )


class ProjectPaymentSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)

        invoices = Invoice.objects.filter(project=project)

        summary = invoices.aggregate(
            total_invoiced=Sum('total_amount'),
            total_paid=Sum('paid_amount'),
            total_balance=Sum('balance_amount')
        )

        return Response({
            "project_id": project.id,
            "project_name": project.name,
            "total_invoiced": summary['total_invoiced'] or 0,
            "total_paid": summary['total_paid'] or 0,
            "total_balance": summary['total_balance'] or 0
        })


class ProjectPaymentsListAPIView(APIView):
    """
    Get all payments for a specific project
    
    GET /api/projects/<project_id>/payments/
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_id):
        """Get all payments for a project"""
        project = get_object_or_404(Project, project_no=project_id)
        
        # Get all invoices for this project
        invoices = project.invoice_set.all()
        
        # Get all payments for those invoices
        payments = InvoicePayment.objects.filter(
            invoice__in=invoices
        ).select_related('created_by', 'invoice').order_by('-payment_date')
        
        # Build payment data
        payment_data = []
        for payment in payments:
            payment_data.append({
                'id': payment.id,
                'invoice_id': payment.invoice.id,
                'invoice_no': payment.invoice.invoice_no,
                'payment_date': payment.payment_date,
                'amount': str(payment.amount),
                'payment_method': payment.get_payment_method_display(),
                'reference_no': payment.reference_no,
                'notes': payment.notes,
                'created_by_name': payment.created_by.get_full_name() if payment.created_by else None,
                'created_at': payment.created_at
            })
        
        # Calculate totals
        total_payments = sum(float(p['amount']) for p in payment_data)
        
        return Response({
            'project_no': project.project_no,
            'project_name': project.project_name,
            'invoice_count': invoices.count(),
            'total_invoiced': str(invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0),
            'total_payments': str(total_payments),
            'payment_count': len(payment_data),
            'payments': payment_data
        }, status=status.HTTP_200_OK)
from .serializers import (
    PurchaseOrderCreateSerializer,
    PurchaseOrderSerializer
)
from .models import PurchaseOrder, PurchaseOrderItem
from product_group.models import Quote, QuoteItem   
from accounts.models import Account,Vendor



class PurchaseOrderCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]    
    @transaction.atomic
    def post(self, request):
        """
        Create Purchase Order from Quote
        """

        # 🔒 Validate required fields
        quote_no = request.data.get("quote_no")
        vendor_id = request.data.get("vendor_id")
        items = request.data.get("items", [])

        if not quote_no:
            return Response(
                {"error": "quote_no is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not vendor_id:
            return Response(
                {"error": "vendor_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not items:
            return Response(
                {"error": "At least one item is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 🔗 Fetch objects safely
        quote = get_object_or_404(Quote, quote_no=quote_no)
        vendor = get_object_or_404(Vendor, id=vendor_id)

        # 🔢 Generate PO number
        po_no = f"PO-{quote.quote_no}-{PurchaseOrder.objects.count() + 1}"

        # 🧾 Create Purchase Order
        po = PurchaseOrder.objects.create(
            po_no=po_no,
            quote=quote,
            project=quote.project,
            vendor=vendor,
            created_by=request.user,
            issue_date=timezone.now()
        )

        total = Decimal("0.00")

        # 📦 Create PO Items
        for item in items:
            quote_item_id = item.get("quote_item_id")
            quantity = item.get("quantity")
            unit_rate = item.get("unit_rate")  # optional

            if not quote_item_id or not quantity:
                return Response(
                    {"error": "quote_item_id and quantity are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            quote_item = get_object_or_404(
                QuoteItem,
                id=quote_item_id,
                quote=quote
            )

            # ✅ SAFE DEFAULT (IMPORTANT FIX)
            unit_rate = Decimal(unit_rate) if unit_rate else quote_item.price_per_unit

            if unit_rate is None:
                return Response(
                    {
                        "detail": f"unit_rate missing for quote_item {quote_item.id}"
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            po_item = PurchaseOrderItem.objects.create(
                purchase_order=po,
                quote_item=quote_item,
                description=quote_item.description,
                quantity=Decimal(quantity),
                unit_rate=unit_rate
            )

            total += po_item.amount

        # 🔢 Update totals
        po.sub_total = total
        po.total_amount = total
        po.save()

        return Response(
            {
                "message": "Purchase Order created successfully",
                "po_no": po.po_no,
                "total_amount": po.total_amount
            },
            status=status.HTTP_201_CREATED
        )
class ProjectPurchaseOrderListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_no):
        project = get_object_or_404(Project, project_no=project_no)

        purchase_orders = (
            PurchaseOrder.objects
            .filter(project=project)
            .select_related("vendor", "quote", "created_by")
            .prefetch_related("items")
            .order_by("-issue_date")
        )

        return Response({
            "project_no": project.project_no,
            "project_name": project.project_name,
            "count": purchase_orders.count(),
            "purchase_orders": [
                {
                    "po_id": po.id,
                    "po_no": po.po_no,
                    "vendor_name": po.vendor.name,
                    "status": po.status,
                    "total_amount": po.total_amount,
                    "items_count": po.items.count(),
                    "issue_date": po.issue_date
                }
                for po in purchase_orders
            ]
        })



class QuotePurchaseOrderListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    # def get(self, request, quote_id):
    #     purchase_orders = PurchaseOrder.objects.filter(
    #         quote_id=quote_id
    #     ).prefetch_related('items')

    #     serializer = PurchaseOrderSerializer(purchase_orders, many=True)
        # return Response(serializer.data)

    def get(self, request, quote_id):
        purchase_orders = (
            PurchaseOrder.objects
            .filter(quote_id=quote_id)
            .select_related('vendor', 'created_by', 'project')
            .prefetch_related('items') 
        )

        serializer = PurchaseOrderSerializer(purchase_orders, many=True)
        return Response(serializer.data)

class PurchaseOrderDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, po_id):
        po = get_object_or_404(PurchaseOrder, id=po_id)
        serializer = PurchaseOrderSerializer(po)
        return Response(serializer.data)
class PurchaseOrderStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, po_id):
        po = get_object_or_404(PurchaseOrder, id=po_id)

        status_value = request.data.get('status')
        if status_value not in dict(PurchaseOrder.STATUS_CHOICES):
            return Response(
                {"detail": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST
            )

        po.status = status_value
        po.save(update_fields=['status'])

        return Response({
            "message": "Status updated",
            "status": po.status
        })


from django.shortcuts import get_object_or_404


from finances.models import VendorBill, PurchaseOrder


class VendorBillCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request):
        purchase_order_id = request.data.get("purchase_order_id")

        if not purchase_order_id:
            return Response(
                {"error": "purchase_order_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        po = get_object_or_404(PurchaseOrder, id=purchase_order_id)

        if VendorBill.objects.filter(purchase_order=po).exists():
            return Response(
                {"error": "Vendor bill already exists for this purchase order"},
                status=status.HTTP_400_BAD_REQUEST
            )

        bill = VendorBill.objects.create(
            bill_no=f"BILL-{po.po_no}",
            vendor=po.vendor,
            purchase_order=po,
            bill_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
        )

        return Response(
            {
                "message": "Vendor bill created successfully",
                "bill_id": bill.id,
                "bill_no": bill.bill_no,
                "total_amount": bill.total_amount,
                "status": bill.status
            },
            status=status.HTTP_201_CREATED
        )
    


from finances.models import VendorBill


class VendorBillListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        qs = VendorBill.objects.select_related(
            'vendor', 'purchase_order', 'purchase_order__project'
        ).order_by('-bill_date')

        vendor_id = request.query_params.get("vendor_id")
        status_ = request.query_params.get("status")
        project_id = request.query_params.get("project_id")

        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)

        if status_:
            qs = qs.filter(status=status_)
            
        if project_id:
            qs = qs.filter(purchase_order__project__project_no=project_id)

        data = [
            {
                "id": bill.id,
                "bill_no": bill.bill_no,
                "vendor": bill.vendor.name,
                "vendor_id": bill.vendor.id,
                "po_no": bill.purchase_order.po_no,
                "project_no": bill.purchase_order.project.project_no,
                "project_name": bill.purchase_order.project.project_name,
                "total_amount": float(bill.total_amount),
                "paid_amount": float(bill.paid_amount),
                "balance_amount": float(bill.balance_amount),
                "status": bill.status,
                "bill_date": str(bill.bill_date),
                "due_date": str(bill.due_date),
            }
            for bill in qs
        ]

        return Response({
            "count": len(data),
            "bills": data
        })
    
class VendorBillByNumberAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, bill_no):
        bill = get_object_or_404(
            VendorBill.objects.select_related("vendor", "purchase_order"),
            bill_no=bill_no
        )

        data = {
            "id": bill.id,
            "bill_no": bill.bill_no,
            "vendor": {
                "id": bill.vendor.id,
                "name": bill.vendor.name,
            },
            "purchase_order": {
                "id": bill.purchase_order.id,
                "po_no": bill.purchase_order.po_no,
            } if bill.purchase_order else None,
            "total_amount": bill.total_amount,
            "paid_amount": bill.paid_amount,
            "balance_amount": bill.balance_amount,
            "status": bill.status,
            "bill_date": bill.bill_date,
            "due_date": bill.due_date,
        }

        return Response(data)



from finances.models import VendorBill, OutgoingPayment


class OutgoingPaymentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    @transaction.atomic
    def post(self, request, bill_id):
        bill = get_object_or_404(VendorBill, id=bill_id)

        amount = request.data.get("amount")
        payment_date = request.data.get("payment_date")
        payment_method = request.data.get("payment_method")
        reference_no = request.data.get("reference_no", "")

        if not amount or not payment_date or not payment_method:
            return Response(
                {"error": "amount, payment_date and payment_method are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if float(amount) <= 0:
            return Response(
                {"error": "Payment amount must be greater than zero"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if float(amount) > float(bill.balance_amount):
            return Response(
                {"error": "Payment exceeds bill balance"},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = OutgoingPayment.objects.create(
            vendor_bill=bill,
            vendor=bill.vendor,
            payment_date=payment_date,
            amount=amount,
            payment_method=payment_method,
            reference_no=reference_no
        )

        return Response(
            {
                "message": "Payment recorded successfully",
                "payment_id": payment.id,
                "bill_no": bill.bill_no,
                "paid_amount": payment.amount,
                "remaining_balance": bill.balance_amount
            },
            status=status.HTTP_201_CREATED
        )


from finances.models import OutgoingPayment


class VendorBillPaymentListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, bill_id):
        # ✅ Validate bill exists
        bill = get_object_or_404(VendorBill, id=bill_id)
        
        payments = OutgoingPayment.objects.filter(
            vendor_bill_id=bill_id
        ).select_related('vendor', 'vendor_bill').order_by('-payment_date')

        data = [
            {
                "id": p.id,
                "bill_no": p.vendor_bill.bill_no,
                "vendor": p.vendor.name,
                "amount": p.amount,
                "payment_method": p.payment_method,
                "reference_no": p.reference_no,
                "payment_date": p.payment_date,
                "created_at": p.created_at,
            }
            for p in payments
        ]

        return Response({
            "bill_id": bill.id,
            "bill_no": bill.bill_no,
            "vendor": bill.vendor.name,
            "total_amount": bill.total_amount,
            "paid_amount": bill.paid_amount,
            "remaining_amount": bill.balance_amount,
            "count": len(data),
            "payments": data
        })

from finances.models import OutgoingPayment


class ProjectOutgoingPaymentsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, project_id):
        # ✅ Project uses project_no as primary key
        project = get_object_or_404(Project, project_no=project_id)

        # 🔍 DEBUG: Check what POs exist for this project
        pos = PurchaseOrder.objects.filter(project=project)
        
        # 🔍 DEBUG: Check what bills exist for those POs
        bills = VendorBill.objects.filter(purchase_order__in=pos)
        
        # 🔍 Get payments
        payments = OutgoingPayment.objects.filter(
            vendor_bill__in=bills
        ).select_related(
            'vendor', 'vendor_bill', 'vendor_bill__purchase_order'
        ).order_by('-payment_date')

        total_paid = payments.aggregate(
            total=Sum('amount')
        )['total'] or 0

        data = {
            "project_no": project.project_no,
            "project_name": project.project_name,
            "debug": {
                "purchase_order_count": pos.count(),
                "vendor_bill_count": bills.count(),
            },
            "total_paid": float(total_paid),
            "payment_count": payments.count(),
            "payments": [
                {
                    "id": p.id,
                    "bill_no": p.vendor_bill.bill_no,
                    "po_no": p.vendor_bill.purchase_order.po_no,
                    "vendor": p.vendor.name,
                    "amount": float(p.amount),
                    "payment_method": p.payment_method,
                    "reference_no": p.reference_no,
                    "payment_date": str(p.payment_date),
                    "created_at": str(p.created_at),
                }
                for p in payments
            ]
        }

        return Response(data)


class SendPurchaseOrderEmailView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, po_id):
        po = get_object_or_404(PurchaseOrder, pk=po_id)

        if not po.vendor.email:
            return Response(
                {"error": "Vendor email not found"},
                status=status.HTTP_400_BAD_REQUEST
            )

        send_purchase_order_email.delay(po.id)

        return Response(
            {"message": "Purchase Order email sent successfully"},
            status=status.HTTP_200_OK
        )


class ProjectAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    def post(self, request, project_id):
        # Extract file separately to avoid deepcopy pickle errors
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"file": ["This field is required."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build clean data without file
        data = {
            "project": project_id,
            "category": request.POST.get("category", ""),
        }

        # Create serializer with file and data separately
        serializer = ProjectAttachmentSerializer(
            data=data,
            context={"user": request.user, "file": uploaded_file}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def get(self, request, project_id=None, attachment_id=None):
        # If attachment_id is provided, fetch single attachment
        if attachment_id:
            attachment = get_object_or_404(ProjectAttachment, id=attachment_id)
            serializer = ProjectAttachmentSerializer(attachment, context={'request': request})
            return Response(serializer.data)
        
        # Otherwise fetch by project_id
        if not project_id:
            return Response(
                {"error": "Either project_id or attachment_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        category = request.GET.get("category")

        attachments = ProjectAttachment.objects.filter(
            project_id=project_id
        )

        if category:
            attachments = attachments.filter(category=category)

        serializer = ProjectAttachmentSerializer(attachments, many=True, context={'request': request})
        return Response(serializer.data)

    def download(self, request, attachment_id):
        """Download an attachment file"""
        attachment = get_object_or_404(ProjectAttachment, id=attachment_id)
        
        if not attachment.file:
            return Response(
                {"error": "File not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return FileResponse(
            attachment.file.open('rb'),
            as_attachment=True,
            filename=attachment.file_name,
            content_type=attachment.file_type
        )





    def delete(self, request, attachment_id):
        attachment = get_object_or_404(
            ProjectAttachment,
            id=attachment_id
        )

        attachment.delete()
        return Response(
            {"message": "Attachment deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )

# class DownloadAttachmentView(APIView):
#     """Download attachment file"""
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]

#     def get(self, request, attachment_id):
#         import requests
#         from io import BytesIO
        
#         attachment = get_object_or_404(ProjectAttachment, id=attachment_id)
        
#         if not attachment.file:
#             return Response(
#                 {"error": "File not found"},
#                 status=status.HTTP_404_NOT_FOUND
#             )
        
#         # Get the Cloudinary URL and download the file
#         file_url = attachment.file.url
#         response = requests.get(file_url)
        
#         if response.status_code != 200:
#             return Response(
#                 {"error": "Failed to download file"},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
        
#         return FileResponse(
#             BytesIO(response.content),
#             as_attachment=True,
#             filename=attachment.file_name,
#             content_type=attachment.file_type
#         )

# views.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework import status

from .models import ProjectAttachment
from .serializers import ProjectAttachmentSerializer

class UploadAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        serializer = ProjectAttachmentSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# import time
# import cloudinary.utils

# from django.shortcuts import get_object_or_404
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# from rest_framework_simplejwt.authentication import JWTAuthentication
# from rest_framework.response import Response
# from rest_framework import status

# from .models import ProjectAttachment


# class DownloadAttachmentView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]

#     def get(self, request, attachment_id):
#         attachment = get_object_or_404(ProjectAttachment, id=attachment_id)

#         signed_url, _ = cloudinary.utils.cloudinary_url(
#             attachment.file.public_id,
#             resource_type="raw",
#             format="pdf",          # required (your public_id has no .pdf)
#             sign_url=True,
#             expires_at=int(time.time()) + 300
#         )

#         return Response(
#             {
#                 "file_name": attachment.file_name,
#                 "download_url": signed_url
#             },
#             status=status.HTTP_200_OK
#         )
import time
import cloudinary.utils
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework import status
from .models import ProjectAttachment
from django.http import HttpResponse
import requests


# class DownloadAttachmentView(APIView):
#     permission_classes = [IsAuthenticated]
#     authentication_classes = [JWTAuthentication]



#     def get(self, request, attachment_id):
#         attachment = get_object_or_404(ProjectAttachment, id=attachment_id)
        
#         signed_url, _ = cloudinary.utils.cloudinary_url(
#             attachment.file.public_id,
#             resource_type="raw",
#             sign_url=True,
#             expires_at=int(time.time()) + 3600
#         )
        
#         # Download from Cloudinary
#         response = requests.get(signed_url, stream=True)
        
#         # Stream to client
#         django_response = HttpResponse(
#             response.content,
#             content_type=response.headers.get('content-type', 'application/octet-stream')
#         )
#         django_response['Content-Disposition'] = f'attachment; filename="{attachment.file_name}"'
        
#         return django_response





import time
import cloudinary.utils
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response

from .models import ProjectAttachment


class DownloadAttachmentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request, attachment_id):
        attachment = get_object_or_404(ProjectAttachment, id=attachment_id)

        signed_url, _ = cloudinary.utils.cloudinary_url(
            attachment.file.public_id,
            resource_type="raw",
            format="pdf",
            sign_url=True,
            expires_at=int(time.time()) + 300
        )

        return Response({
            "file_name": attachment.file_name,
            "download_url": signed_url
        })
class ExpenseAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
      
        if pk:
            expense = get_object_or_404(Expense, pk=pk)
            serializer = ExpenseSerializer(expense)
            return Response(serializer.data)

        # 🔹 LIST / FILTER
        queryset = Expense.objects.all()

        project_id = request.query_params.get('project')
        category = request.query_params.get('category')
        is_paid = request.query_params.get('paid')

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        if category:
            queryset = queryset.filter(category=category)

        # 🔥 Annotate total paid (DB-level)
        queryset = queryset.annotate(
            total_paid_db=Coalesce(Sum('payments__amount'), 0)
        )

        if is_paid == 'true':
            queryset = queryset.filter(total_paid_db__gte=F('amount'))

        elif is_paid == 'false':
            queryset = queryset.filter(total_paid_db__lt=F('amount'))

        serializer = ExpenseSerializer(queryset, many=True)
        return Response(serializer.data)

    # ➕ CREATE EXPENSE
    def post(self, request):
        serializer = ExpenseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    def put(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        serializer = ExpenseSerializer(expense, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class ExpensePaymentAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # 💰 ADD PAYMENT
    def put(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk)
        serializer = ExpensePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save(expense=expense)
        except ValidationError as e:
            raise DRFValidationError({"error": e.messages})

        return Response(
            {
                "message": "Payment added successfully",
                "total_paid": expense.total_paid(),
                "balance_amount": expense.balance_amount(),
                "is_fully_paid": expense.is_fully_paid()
            },
            status=status.HTTP_200_OK
        )

class ProjectExpenseListAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        expenses = Expense.objects.filter(project_id=project_id).order_by('-expense_date')

        serializer = ProjectExpenseListSerializer(expenses, many=True)

        return Response(
            {
                "project_id": project_id,
                "expenses": serializer.data
            },
            status=status.HTTP_200_OK
        )

class ExpenseCategoryAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        categories = [
            {"key": key, "label": label}
            for key, label in Expense.CATEGORY_CHOICES
        ]

        return Response(categories)
