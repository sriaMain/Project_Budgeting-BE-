from django.shortcuts import render
from .models import ProductGroup, Product_Services
from .serializers import ProductGroupSerializer, ProductServicesSerializer
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