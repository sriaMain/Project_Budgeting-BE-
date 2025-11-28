from django.db import models

# Create your models here.
class Module(models.Model):
    module_name = models.CharField(max_length=50)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='modules_created', null=True)
    modified_by = models.ForeignKey(
        'accounts.Account', on_delete=models.SET_NULL, related_name='modules_updated', null=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.module_name
    

