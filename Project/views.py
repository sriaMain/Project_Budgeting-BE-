

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Project, ProjectBudget
from .serializers import ProjectSerializer, ProjectBudgetSerializer



# Single CBV for all CRUD operations for Project
class ProjectAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated]
	authentication_classes = [JWTAuthentication]

	def get(self, request, pk=None):
		if pk is not None:
			try:
				project = Project.objects.get(pk=pk)
			except Project.DoesNotExist:
				return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
			serializer = ProjectSerializer(project)
			print('DEBUG Project GET:', serializer.data)  # Debug print
			return Response(serializer.data)
		else:
			projects = Project.objects.all()
			serializer = ProjectSerializer(projects, many=True)
			print('DEBUG Project LIST:', serializer.data)  # Debug print
			return Response(serializer.data)

	def post(self, request, pk=None):
		serializer = ProjectSerializer(data=request.data)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_201_CREATED)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# Single CBV for all CRUD operations for ProjectBudget
class ProjectBudgetAPIView(APIView):
	permission_classes = [permissions.IsAuthenticated]
	authentication_classes = [JWTAuthentication]


	def get(self, request, project_no=None):
		if project_no is not None:
			try:
				budget = ProjectBudget.objects.get(project__project_no=project_no)
			except ProjectBudget.DoesNotExist:
				return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
			serializer = ProjectBudgetSerializer(budget)
			return Response(serializer.data)
		else:
			budgets = ProjectBudget.objects.all()
			serializer = ProjectBudgetSerializer(budgets, many=True)
			return Response(serializer.data)

	def post(self, request, project_no=None):
		data = request.data.copy()
		if project_no is not None:
			# Set the project by project_no (which is the PK)
			try:
				project = Project.objects.get(project_no=project_no)
				data['project'] = project.project_no
			except Project.DoesNotExist:
				return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)
		serializer = ProjectBudgetSerializer(data=data)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data, status=status.HTTP_201_CREATED)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def put(self, request, project_no=None):
		if project_no is None:
			return Response({'detail': 'Method "PUT" not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
		try:
			project = Project.objects.get(project_no=project_no)
			budget = ProjectBudget.objects.get(project=project)
		except (Project.DoesNotExist, ProjectBudget.DoesNotExist):
			return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
		serializer = ProjectBudgetSerializer(budget, data=request.data)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data)
		return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

	def delete(self, request, project_no=None):
		if project_no is None:
			return Response({'detail': 'Method "DELETE" not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
		try:
			project = Project.objects.get(project_no=project_no)
			budget = ProjectBudget.objects.get(project=project)
		except (Project.DoesNotExist, ProjectBudget.DoesNotExist):
			return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
		budget.delete()
		return Response(status=status.HTTP_204_NO_CONTENT)