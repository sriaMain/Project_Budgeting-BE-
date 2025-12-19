
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class Project(models.Model):
	PROJECT_TYPE_CHOICES = [
		('internal', 'Internal'),
		('external', 'External'),
	]
	CURRENCY_CHOICES = [
		('INR', 'INR'),
		('USD', 'USD'),
		('EUR', 'EUR'),
	]

	project_no = models.AutoField(primary_key=True)
	project_name = models.CharField(max_length=255)
	project_type = models.CharField(max_length=20, choices=PROJECT_TYPE_CHOICES)
	client = models.ForeignKey('client.Company', on_delete=models.SET_NULL, null=True, blank=True)
	currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='INR')
	start_date = models.DateField()
	end_date = models.DateField()
	project_manager = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, null=True, blank=True)
	created_from_quotation = models.ForeignKey('product_group.Quote', on_delete=models.SET_NULL, null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	modified_at = models.DateTimeField(auto_now=True)

	def save(self, *args, **kwargs):
		# Auto-generate project number if not set
		# if not self.project_no:
		# 	from datetime import datetime
		# 	today = datetime.now().strftime('%Y%m%d')
		# 	last = Project.objects.filter(project_no__startswith=f'PRJ-{today}').count() + 1
		# 	self.project_no = f'PRJ-{today}-{last:03d}'

		# Auto-assign client and project_manager from quotation if available
		if self.created_from_quotation:
			if hasattr(self.created_from_quotation, 'client'):
				self.client = self.created_from_quotation.client
			if hasattr(self.created_from_quotation, 'project_manager'):
				self.project_manager = self.created_from_quotation.project_manager

		if self.end_date < self.start_date:
			raise ValidationError(_('End date cannot be before start date.'))
		super().save(*args, **kwargs)

	def __str__(self):
		return f"{self.project_name} ({self.project_no})"


class ProjectBudget(models.Model):
	project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='budget')
	use_quoted_amounts = models.BooleanField(default=True)
	total_hours = models.PositiveIntegerField(null=True, blank=True)
	total_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	bills_and_expenses = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
	currency = models.CharField(max_length=10, choices=Project.CURRENCY_CHOICES, default='INR')
	created_at = models.DateTimeField(auto_now_add=True)
	modified_at = models.DateTimeField(auto_now=True)


	def clean(self):
		if not self.use_quoted_amounts:
			if self.total_hours is None or self.total_budget is None:
				raise ValidationError(_('Total hours and total budget must be filled when setting manually.'))
		else:
			# If using quoted amounts, these should be fetched from the related quotation
			if not self.project.created_from_quotation:
				raise ValidationError(_('No quotation linked to fetch quoted amounts.'))

	def fetch_quoted_amounts(self):
		# Fetch from quotation if available
		quotation = self.project.created_from_quotation
		if quotation:
			# Sum hours from related QuoteItems with unit='hours'
			items = getattr(quotation, 'items', None)
			if items is not None:
				self.total_hours = sum(item.quantity for item in items.all() if getattr(item, 'unit', None) == 'hours')
			else:
				self.total_hours = 0
			# Use total_amount from Quote for total_budget
			self.total_budget = getattr(quotation, 'total_amount', 0)
			# Use in_house_cost + outsourced_cost for bills_and_expenses
			in_house_cost = getattr(quotation, 'in_house_cost', 0)
			outsourced_cost = getattr(quotation, 'outsourced_cost', 0)
			try:
				self.bills_and_expenses = in_house_cost + outsourced_cost
			except Exception:
				self.bills_and_expenses = 0
			self.currency = getattr(quotation, 'currency', 'INR')
		else:
			raise ValidationError(_('No quotation linked to fetch quoted amounts.'))

	def save(self, *args, **kwargs):
		self.full_clean()
		super().save(*args, **kwargs)
