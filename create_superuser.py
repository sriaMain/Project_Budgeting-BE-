# create_superuser.py
import os
import django
 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()
 
from django.contrib.auth import get_user_model
 
User = get_user_model()
 
username = "admin"
email = "teerdaveni@sriainfotech.com"
password = "Admin@123"   # change to a strong password
 
 
 
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superuser created!")
else:
    print("Superuser already exists.")
 
 