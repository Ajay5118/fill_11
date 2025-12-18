"""
Auto-create superuser for FILL11
Works with custom User model (phone + name required)
Save as: create_superuser.py in project root
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fill11.settings')
django.setup()

from apps.users.models import User

# Get credentials from environment variables
phone = os.environ.get('DJANGO_SUPERUSER_PHONE', '+919999999999')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@fill11.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
name = os.environ.get('DJANGO_SUPERUSER_NAME', 'Admin User')

# Check if superuser already exists (by phone or email)
if User.objects.filter(phone=phone).exists():
    print(f'ℹ️  User with phone {phone} already exists.')
elif email and User.objects.filter(email=email).exists():
    print(f'ℹ️  User with email {email} already exists.')
else:
    try:
        # Use the custom create_superuser method
        # Based on your UserManager, it requires: phone, name, password
        user = User.objects.create_superuser(
            phone=phone,
            name=name,
            password=password,
            email=email  # Optional field
        )
        print(f'✅ Superuser created successfully!')
        print(f'   Phone: {phone}')
        print(f'   Name: {name}')
        print(f'   Email: {email}')
        print(f'\n🔐 Login at: https://fill-11.onrender.com/admin/')

    except Exception as e:
        print(f'❌ Error creating superuser: {e}')
        import traceback

        traceback.print_exc()