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


def get_first_error_message(errors):
    """
    Extracts the first error message from a DRF serializer error dictionary.
    """
    if not isinstance(errors, dict):
        if isinstance(errors, list) and errors:
            return errors[0]
        return str(errors)

    if 'non_field_errors' in errors and errors['non_field_errors']:
        return errors['non_field_errors'][0]

    for field, messages in errors.items():
        if isinstance(messages, list) and messages:
            return messages[0]
            
    return "An unknown validation error occurred."


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
        try:
            serializer = CompanySerializer(data=request.data)

            if serializer.is_valid():
                company = serializer.save()
                read_serializer = CompanySerializer(company)
                return Response(read_serializer.data, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        try:
            serializer = PointOfContactSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            poc = serializer.save()
            return Response(
                PointOfContactSerializer(poc).data,
                status=status.HTTP_201_CREATED,
            )
        except DRFValidationError as e:
            error_message = get_first_error_message(e.detail)
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

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
        try:
            poc = self.get_object(pk)
            serializer = PointOfContactSerializer(poc, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_poc = serializer.save()
            return Response(
                PointOfContactSerializer(updated_poc).data,
                status=status.HTTP_200_OK,
            )
        except DRFValidationError as e:
            error_message = get_first_error_message(e.detail)
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response(
                {"error": f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, pk):
        try:
            poc = self.get_object(pk)
            serializer = PointOfContactSerializer(poc, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            updated_poc = serializer.save()
            return Response(
                PointOfContactSerializer(updated_poc).data,
                status=status.HTTP_200_OK,
            )
        except DRFValidationError as e:
            error_message = get_first_error_message(e.detail)
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)

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
