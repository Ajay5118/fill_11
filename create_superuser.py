"""
Auto-create superuser if it doesn't exist
Save as: create_superuser.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fill11.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@fill11.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'✅ Superuser "{username}" created successfully!')
else:
    print(f'ℹ️  Superuser "{username}" already exists.')