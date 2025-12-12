
from .serializers import QuoteSummarySerializer
from .models import Quote
from django.db.models import Avg, Sum, Count


from django.shortcuts import render
from django.http import Http404
from .models import ProductGroup, Product_Services, Quote
from .serializers import ProductGroupSerializer, ProductServicesSerializer, QuoteSerializer, ProductGroupWithModulesSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .tasks import send_quote_email

class ProductGroupListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        # If pk is provided → return single product group
        if pk is not None:
            try:
                product_group = ProductGroup.objects.get(pk=pk)
            except ProductGroup.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = ProductGroupSerializer(product_group)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # If no pk → return all product groups
        product_groups = ProductGroup.objects.all()
        serializer = ProductGroupSerializer(product_groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ProductGroupSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk):
        try:
            product_group = ProductGroup.objects.get(pk=pk)
        except ProductGroup.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductGroupSerializer(product_group, partial=True, data=request.data)
        if serializer.is_valid():
            serializer.save(modified_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def delete(self, request, pk):
        try:
            product_group = ProductGroup.objects.get(pk=pk)
        except ProductGroup.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        product_group.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    


class ProductServicesView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # Similar methods for Product_Services can be implemented here
    def get(self, request, pk=None):
        if pk is not None:
            try:
                product_services = Product_Services.objects.get(pk=pk)
            except ProductGroup.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = ProductServicesSerializer(product_services)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # If no pk → return all product groups
        product_services = Product_Services.objects.all()
        serializer = ProductServicesSerializer(product_services, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        serializer = ProductServicesSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def put(self, request, pk):
        try:
            product_services = Product_Services.objects.get(pk=pk)
        except Product_Services.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductServicesSerializer(product_services, partial=True, data=request.data)
        if serializer.is_valid():
            serializer.save(modified_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def delete(self, request, pk):
        try:
            product_services = Product_Services.objects.get(pk=pk)
        except Product_Services.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        product_services.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    

class ProductGroupNameListView(APIView):
    """
    API view to get a list of only the product group names.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Use values_list with flat=True to get a simple list of strings
        names = ProductGroup.objects.order_by('product_group_name').values_list('product_group_name', flat=True)
        return Response(names, status=status.HTTP_200_OK)
    
class ProductGroupWithModulesListView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        groups = ProductGroup.objects.all()
        serializer = ProductGroupWithModulesSerializer(groups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
from rest_framework.permissions import AllowAny
class PipelineDataAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        quotes = Quote.objects.all()

        # Stats
        total_quotes = quotes.count()
        average_quote = quotes.aggregate(avg=Avg('total_amount'))['avg'] or 0
        total_sum = quotes.aggregate(sum=Sum('total_amount'))['sum'] or 0
        # For demo, margin is not calculated, set to 0
        total_margin = 0

        # Group quotes by stage/status
        stages = []
        for stage in ['Oppurtunity', 'Scoping', 'Proposal', 'Confirmed']:
            stage_quotes = quotes.filter(status__iexact=stage)
            serializer = QuoteSummarySerializer(stage_quotes, many=True)
            stages.append({
                'stage': stage.lower(),
                'title': stage.capitalize(),
                'count': stage_quotes.count(),
                'total_sum': float(stage_quotes.aggregate(sum=Sum('total_amount'))['sum'] or 0),
                'quotes': serializer.data
            })

        data = {
            'stats': {
                'total_quotes': total_quotes,
                'average_quote': float(average_quote),
                'total_sum': float(total_sum),
                'total_margin': float(total_margin)
            },
            'stages': stages
        }
        return Response(data)
    

from rest_framework.permissions import AllowAny
from .models import QuoteItem
class QuoteStatusChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        choices = [{"value": c[0], "label": c[1]} for c in Quote.STATUS_CHOICES]
        return Response(choices)
    
class QuoteItemUnitChoicesView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        choices = [{"value": c[0], "label": c[1]} for c in QuoteItem.UNIT_CHOICES]
        return Response(choices)
    

# --- QUOTATION VIEWS ---

class QuoteListCreateView(APIView):
    """
    API view to list all quotes or create a new one.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        quotes = Quote.objects.all().order_by('-date_of_issue')
        serializer = QuoteSerializer(quotes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = QuoteSerializer(data=request.data)
        if serializer.is_valid():
            # Pass the user from the request to the serializer's create method
            serializer.save(created_by=request.user, author=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuoteDetailView(APIView):
    """
    API view to retrieve, update or delete a quote instance.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Quote.objects.get(pk=pk)
        except Quote.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        quote = self.get_object(pk)
        from .serializers import QuoteDetailSerializer
        serializer = QuoteDetailSerializer(quote)
        return Response(serializer.data)

    def put(self, request, pk):
        quote = self.get_object(pk)
        serializer = QuoteSerializer(quote, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(modified_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        quote = self.get_object(pk)
        quote.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendQuoteEmailView(APIView):
    """
    A view to send the quote details to the client via email.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Quote.objects.get(pk=pk)
        except Quote.DoesNotExist:
            raise Http404

    # def post(self, request, pk):
    #     quote = self.get_object(pk)

    #     # Check if there's a point of contact with an email
    #     if not quote.client or not quote.client.email:
    #         return Response(
    #             {"error": "No Point of Contact with an email address is associated with this quote."},
    #             status=status.HTTP_400_BAD_REQUEST
    #         )

    #     # Prepare email context
    #     subject = f"Quotation: {quote.quote_name} (Ref: {quote.quote_no})"
    #     recipient_email = quote.client.email
        
    #     # For now, we'll send a simple text email. We can create an HTML template later.
    #     message = f"""
    #     Dear {quote.client.company_name},

    #     Please find the details of your quotation '{quote.quote_name}' below.

    #     Quote No: {quote.quote_no}
    #     Total Amount: {quote.total_amount}
    #     Due Date: {quote.due_date.strftime('%d-%b-%Y')}

    #     Thank you for your business.

    #     Best regards,
    #     {request.user.first_name or 'Your Company'}
    #     """

        
    #     send_quote_email(subject, message, recipient_email)
    #     return Response({"success": f"Quote is being sent to {recipient_email}."}, status=status.HTTP_200_OK)

    def post(self, request, pk):
        quote = self.get_object(pk)

        if not quote.client or not quote.client.email:
            return Response(
                {"error": "No Point of Contact with an email address is associated with this quote."},
                status=status.HTTP_400_BAD_REQUEST
            )

        subject = f"Quotation: {quote.quote_name} (Ref: {quote.quote_no})"
        recipient_email = quote.client.email

        # Generate public link (set FRONTEND_BASE_URL in your settings.py)
        from django.conf import settings
        public_link = f"{settings.FRONTEND_BASE_URL}/pipeline/quote/{pk}/"

        message = f"""
        Dear {quote.client.company_name},

        Please find the details of your quotation '{quote.quote_name}' below.

        Quote No: {quote.quote_no}
        Total Amount: {quote.total_amount}
        Due Date: {quote.due_date.strftime('%d-%b-%Y')}

        You can view your quote online here:
        {public_link}

        Thank you for your business.

        Best regards,
        {request.user.first_name or 'Your Company'}
        """

        send_quote_email(subject, message, recipient_email)
        return Response({"success": f"Quote is being sent to {recipient_email}.", "link": public_link}, status=status.HTTP_200_OK)
    


# CBV for PDF Invoice Download
class QuoteInvoiceDownloadView(APIView):
    permission_classes = []  # Public access

    def get(self, request, pk):
        from django.template.loader import render_to_string
        from weasyprint import HTML
        from django.http import HttpResponse
        from .models import Quote
        quote = Quote.objects.get(pk=pk)
        import os
        from django.conf import settings
        logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'sria_logo.png')
        context = {
            'quote_no': quote.quote_no,
            'quote_name': quote.quote_name,
            'date_of_issue': quote.date_of_issue,
            'due_date': quote.due_date,
            'status': quote.status,
            'author': quote.author,
            'client_name': quote.client.company_name if quote.client else '',
            'client_address': f"{quote.client.street_address}, {quote.client.city}, {quote.client.state}, {quote.client.country}" if quote.client else '',
            'sub_total': quote.sub_total,
            'tax_percentage': quote.tax_percentage,
            'total_amount': quote.total_amount,
            'total_cost': quote.total_cost,
            'in_house_cost': quote.in_house_cost,
            'outsourced_cost': quote.outsourced_cost,
            'invoiced_sum': quote.invoiced_sum,
            'to_be_invoiced_sum': quote.to_be_invoiced_sum,
            'items': quote.items.all(),
            'logo_path': logo_path,
        }
        html_string = render_to_string('quote_invoice.html', context)
        pdf_file = HTML(string=html_string).write_pdf()
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{quote.quote_no}.pdf"'
        return response