from django.db import models

#creating the models
class Account(models.Model):
    username = models.CharField(max_length=150, unique=True)
    gmail = models.EmailField(unique=True)
    password = models.CharField(max_length=255)  # hashed
    def __str__(self):
        return self.username

