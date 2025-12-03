from django.shortcuts import render

# Create your views here.
from .models import Module
from .serializers import ModuleSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication


class ModuleListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # def get(self, request):
    #     modules = Module.objects.all()
    #     serializer = ModuleSerializer(modules, many=True)
    #     return Response(serializer.data, status=status.HTTP_200_OK)
    
    # def get(self, request, pk):
    #     try:
    #         module = Module.objects.get(pk=pk)
    #     except Module.DoesNotExist:
    #         return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    #     serializer = ModuleSerializer(module)
    #     return Response(serializer.data, status=status.HTTP_200_OK)


    def get(self, request, pk=None):
    # If pk is provided → return single module
        if pk is not None:
            try:
                module = Module.objects.get(pk=pk)
            except Module.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

            serializer = ModuleSerializer(module)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # If no pk → return all modules
        modules = Module.objects.all()
        serializer = ModuleSerializer(modules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


    def post(self, request):
        serializer = ModuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user, updated_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def put(self, request, pk):
        try:
            module = Module.objects.get(pk=pk)
        except Module.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ModuleSerializer(module, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(modified_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

    def delete(self, request, pk):
        try:
            module = Module.objects.get(pk=pk)
        except Module.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        module.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)