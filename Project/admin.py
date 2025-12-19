from django.contrib import admin

# Register your models here.
from .models import Project, ProjectBudget
admin.site.register(Project)
admin.site.register(ProjectBudget)