from rest_framework import serializers
from .models import Project, ProjectBudget

class ProjectBudgetSerializer(serializers.ModelSerializer):
	# project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False)
	class Meta:
		model = ProjectBudget
		fields = [
			'use_quoted_amounts',
			'total_hours',
			'total_budget',
			'bills_and_expenses',
			'currency',
			'project',
		]

	def validate(self, data):
		use_quoted = data.get('use_quoted_amounts', True)
		if not use_quoted:
			for field in ['total_hours', 'total_budget']:
				if data.get(field) in [None, '']:
					raise serializers.ValidationError(f"{field.replace('_', ' ').capitalize()} is required when setting manually.")
		return data
	def create(self, validated_data):
			project = validated_data.get('project', None)
			instance = ProjectBudget(**validated_data)
			if instance.use_quoted_amounts and project:
				instance.project = project
				instance.fetch_quoted_amounts()
			instance.save()
			return instance

	def update(self, instance, validated_data):
			for attr, value in validated_data.items():
				setattr(instance, attr, value)
			if instance.use_quoted_amounts and instance.project:
				instance.fetch_quoted_amounts()
			instance.save()
			return instance

class ProjectSerializer(serializers.ModelSerializer):
	budget = serializers.SerializerMethodField()

	class Meta:
		model = Project
		fields = [
			# 'id',
			'project_no',
			'project_name',
			'project_type',
			'client',
			'start_date',
			'end_date',
			'project_manager',
			'created_from_quotation',
			'created_at',
			'modified_at',
			'budget',
		]
		read_only_fields = ['project_no', 'created_at', 'modified_at']
	def get_budget(self, obj):
		budget = getattr(obj, 'budget', None)
		if budget is not None:
			return ProjectBudgetSerializer(budget).data
		# Return default budget values if none exists
		return {
			'use_quoted_amounts': True,
			'total_hours': 0,
			'total_budget': "0.00",
			'bills_and_expenses': "0.00",
			'currency': "INR"
		}

	def create(self, validated_data):
		from django.core.exceptions import ValidationError as DjangoValidationError
		budget_data = validated_data.pop('budget', None)
		try:
			project = Project.objects.create(**validated_data)
		except DjangoValidationError as e:
			# Convert Django ValidationError to DRF ValidationError
			raise serializers.ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)
		# If manual budget is provided, use it
		if budget_data:
			ProjectBudget.objects.create(project=project, **budget_data)
		# If no manual budget, but created_from_quotation is set, use quotation values
		elif project.created_from_quotation:
			quote = project.created_from_quotation
			# Use Decimal directly to avoid float conversion issues
			total_budget = getattr(quote, 'total_amount', 0)
			print('DEBUG: Creating ProjectBudget with total_budget from quote:', total_budget)
			in_house_cost = getattr(quote, 'in_house_cost', 0)
			outsourced_cost = getattr(quote, 'outsourced_cost', 0)
			try:
				bills_and_expenses = in_house_cost + outsourced_cost
			except Exception:
				bills_and_expenses = 0
			ProjectBudget.objects.create(
				project=project,
				use_quoted_amounts=True,
				total_hours=0,  # No field in quote, set to 0 or map if available
				total_budget=total_budget,
				bills_and_expenses=bills_and_expenses,
				currency=project.currency
			)
		# If neither, no budget is created (default budget will be shown in response)
		return project

	def update(self, instance, validated_data):
		budget_data = validated_data.pop('budget', None)
		for attr, value in validated_data.items():
			setattr(instance, attr, value)
		instance.save()
		if budget_data:
			budget, created = ProjectBudget.objects.get_or_create(project=instance)
			for attr, value in budget_data.items():
				setattr(budget, attr, value)
			budget.save()
		return instance
