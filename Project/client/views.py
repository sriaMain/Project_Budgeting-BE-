from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from django.core.exceptions import ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError


from .models import Company, CompanyTag
from .serializers import CompanySerializer, CompanyTagSerializer
from rest_framework.permissions import AllowAny as All
from .models import POC
from .serializers import PointOfContactSerializer




class CompanyListCreateAPIView(APIView):
    permission_classes = [All]
    def get(self, request):
        try:
            companies = Company.objects.all().order_by("company_name")
            serializer = CompanySerializer(companies, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except DatabaseError:
            return Response(
                {"error": "Database error while fetching companies."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        serializer = CompanySerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            company = serializer.save()
            read_serializer = CompanySerializer(company)
            return Response(read_serializer.data, status=status.HTTP_201_CREATED)
        
        except DRFValidationError as e:
            formatted_errors = {}
            errors = e.detail
            for field, messages in errors.items():
                if isinstance(messages, list) and messages:
                    message = messages[0]
                    field_name = field.replace('_', ' ')
                    if "This field is required." in message:
                        formatted_errors[field] = f"{field_name.lower()} is required"
                    else:
                        formatted_errors[field] = message
            return Response({"errors": formatted_errors}, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CompanyDetailAPIView(APIView):
    permission_classes = [All]
    def get_object(self, pk):
        return get_object_or_404(Company, pk=pk)

    def get(self, request, pk):
        try:
            company = self.get_object(pk)
            serializer = CompanySerializer(company)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Company not found."}, status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request, pk):
        try:
            company = self.get_object(pk)
            serializer = CompanySerializer(company, data=request.data)

            if serializer.is_valid():
                company = serializer.save()
                return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk):
        try:
            company = self.get_object(pk)
            serializer = CompanySerializer(company, data=request.data, partial=True)

            if serializer.is_valid():
                updated_company = serializer.save()
                return Response(CompanySerializer(updated_company).data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            company = self.get_object(pk)
            company.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CompanyTagListCreateAPIView(APIView):
    permission_classes = [All]
    def get(self, request):
        try:
            tags = CompanyTag.objects.all().order_by("name")
            serializer = CompanyTagSerializer(tags, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except DatabaseError:
            return Response(
                {"error": "Database error while fetching tags."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        try:
            serializer = CompanyTagSerializer(data=request.data)

            if serializer.is_valid():
                tag = serializer.save()
                return Response(
                    CompanyTagSerializer(tag).data,
                    status=status.HTTP_201_CREATED,
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            
class CompanyTagDetailAPIView(APIView):
    permission_classes = [All]
    def get_object(self, pk):
        return get_object_or_404(CompanyTag, pk=pk)

    def get(self, request, pk):
        try:
            tag = self.get_object(pk)
            serializer = CompanyTagSerializer(tag)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Tag not found."}, status=status.HTTP_404_NOT_FOUND
            )

    def put(self, request, pk):
        try:
            tag = self.get_object(pk)
            serializer = CompanyTagSerializer(tag, data=request.data)

            if serializer.is_valid():
                updated_tag = serializer.save()
                return Response(CompanyTagSerializer(updated_tag).data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        try:
            tag = self.get_object(pk)
            serializer = CompanyTagSerializer(tag, data=request.data, partial=True)

            if serializer.is_valid():
                updated_tag = serializer.save()
                return Response(CompanyTagSerializer(updated_tag).data, status=status.HTTP_200_OK)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            tag = self.get_object(pk)
            tag.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class PointOfContactListCreateAPIView(APIView):
    permission_classes = [All]
    def get(self, request):
        try:
            pocs = POC.objects.all()
            serializer = PointOfContactSerializer(pocs, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "Failed to fetch POCs."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        serializer = PointOfContactSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            poc = serializer.save()
            return Response(
                PointOfContactSerializer(poc).data,
                status=status.HTTP_201_CREATED,
            )
        except DRFValidationError as e:
            formatted_errors = {}
            errors = e.detail
            for field, messages in errors.items():
                if isinstance(messages, list) and messages:
                    message = messages[0]
                    field_name = field.replace('_', ' ')
                    if "This field is required." in message:
                        formatted_errors[field] = f"{field_name.lower()} is required"
                    else:
                        formatted_errors[field] = message
            return Response({"errors": formatted_errors}, status=status.HTTP_400_BAD_REQUEST)

        except DatabaseError:
            return Response(
                {"error": "Database error while creating POC."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PointOfContactDetailAPIView(APIView):
    permission_classes = [All]
    def get_object(self, pk):
        return get_object_or_404(POC, pk=pk)

    def get(self, request, pk):
        try:
            poc = self.get_object(pk)
            serializer = PointOfContactSerializer(poc)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception:
            return Response(
                {"error": "POC not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    def put(self, request, pk):
        poc = self.get_object(pk)
        serializer = PointOfContactSerializer(poc, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            updated_poc = serializer.save()
            return Response(
                PointOfContactSerializer(updated_poc).data,
                status=status.HTTP_200_OK,
            )
        except DRFValidationError as e:
            formatted_errors = {}
            errors = e.detail
            for field, messages in errors.items():
                if isinstance(messages, list) and messages:
                    message = messages[0]
                    field_name = field.replace('_', ' ')
                    if "This field is required." in message:
                        formatted_errors[field] = f"{field_name.lower()} is required"
                    else:
                        formatted_errors[field] = message
            return Response({"errors": formatted_errors}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        poc = self.get_object(pk)
        serializer = PointOfContactSerializer(poc, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
            updated_poc = serializer.save()
            return Response(
                PointOfContactSerializer(updated_poc).data,
                status=status.HTTP_200_OK,
            )
        except DRFValidationError as e:
            formatted_errors = {}
            errors = e.detail
            for field, messages in errors.items():
                if isinstance(messages, list) and messages:
                    message = messages[0]
                    field_name = field.replace('_', ' ')
                    if "This field is required." in message:
                        formatted_errors[field] = f"{field_name.lower()} is required"
                    else:
                        formatted_errors[field] = message
            return Response({"errors": formatted_errors}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, pk):
        try:
            poc = self.get_object(pk)
            poc.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class CompanyPOCListView(APIView):
    """
    API view to retrieve all Points of Contact for a specific company.
    """
    permission_classes = [All]

    def get(self, request, company_id):
        # Ensure the company exists
        company = get_object_or_404(Company, pk=company_id)
        
        # Filter POCs by the company
        pocs = POC.objects.filter(company=company)
        
        # Serialize the results
        serializer = PointOfContactSerializer(pocs, many=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
