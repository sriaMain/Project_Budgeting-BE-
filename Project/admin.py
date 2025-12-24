from django.contrib import admin

# Register your models here.
from .models import Project, ProjectBudget, Task, Timesheet, TimesheetEntry
admin.site.register(Project)
admin.site.register(ProjectBudget)
admin.site.register(Task)
admin.site.register(Timesheet)
admin.site.register(TimesheetEntry)