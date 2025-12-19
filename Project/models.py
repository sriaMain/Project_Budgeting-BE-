
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
    project = models.OneToOneField(Project, on_delete=models.SET_NULL, null=True, related_name='budget')
    use_quoted_amounts = models.BooleanField(default=True)
    total_hours = models.PositiveIntegerField(null=True, blank=True)
    total_budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    bills_and_expenses = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='INR')

    def apply_quoted_amounts(self):
        quote = self.project.created_from_quotation
        if not quote:
            raise ValidationError("Quotation is required")

        self.total_hours = sum(
            item.quantity for item in quote.items.all()
            if item.unit == 'hours'
        )
        self.total_budget = quote.total_amount
        self.bills_and_expenses = quote.in_house_cost + quote.outsourced_cost
        self.currency = getattr(quote, 'currency', None) or self.project.currency
		# self.currency = getattr(quote, 'currency', None) or self.project.currency

