from django.shortcuts import render
from django.http import Http404
from .models import ProductGroup, Product_Services, Quote
from .serializers import ProductGroupSerializer, ProductServicesSerializer, QuoteSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

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
        serializer = QuoteSerializer(quote)
        return Response(serializer.data)

    def put(self, request, pk):
        quote = self.get_object(pk)
        serializer = QuoteSerializer(quote, data=request.data)
        if serializer.is_valid():
            serializer.save(modified_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        quote = self.get_object(pk)
        quote.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)