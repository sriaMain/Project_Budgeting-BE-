from rest_framework import serializers
from .models import Project, ProjectBudget


class ProjectBudgetSerializer(serializers.ModelSerializer):
	class Meta:
		model = ProjectBudget
		fields = (
			'use_quoted_amounts',
			'total_hours',
			'total_budget',
			'bills_and_expenses',
			'currency',
		)

	def validate(self, data):
		if not data.get('use_quoted_amounts'):
			for field in ['total_hours', 'total_budget']:
				if not data.get(field):
					raise serializers.ValidationError(
						f"{field.replace('_',' ')} is required"
					)
		return data
	
class ProjectCreateSerializer(serializers.ModelSerializer):
	budget = ProjectBudgetSerializer(required=False)

	class Meta:
		model = Project
		fields = (
			'project_no',
			'project_name',
			'project_type',
			'start_date',
			'end_date',
			'project_manager',
			'created_from_quotation',
			'budget',
		)

	def create(self, validated_data):
		budget_data = validated_data.pop('budget', None)

		project = Project.objects.create(**validated_data)

		if budget_data:
			budget = ProjectBudget.objects.create(
				project=project,
				**budget_data
			)
			if budget.use_quoted_amounts:
				budget.apply_quoted_amounts()
				budget.save()

		return project
	def validate (self, data):
		start_date = data.get('start_date')
		end_date = data.get('end_date')
		if start_date and end_date and end_date < start_date:
			raise serializers.ValidationError(
				"End date cannot be before start date."
			)
		return data

	

	
