from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import DatabaseError
from django.core.exceptions import ValidationError

from .models import Company, CompanyTag
from .serializers import CompanySerializer, CompanyTagSerializer


class CompanyListCreateAPIView(APIView):
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
