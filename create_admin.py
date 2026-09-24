import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Rovexa.settings')
django.setup()

from accounts.models import CustomUser

admins = [
    ('Admin176', 'admin176@rovexa.com', 'S5#(@56JlK'),
    ('adminbala', 'admin@rovexa.com', 'bala@2003'),
]

for username, email, password in admins:
    try:
        user = CustomUser.objects.filter(username=username).first()
        if not user:
            CustomUser.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                role='ADMIN'
            )
            print(f"Superuser {username} created successfully with role ADMIN.")
        else:
            user.set_password(password)
            user.role = 'ADMIN'
            user.is_staff = True
            user.is_superuser = True
            user.save()
            print(f"Superuser {username} verified and updated to role ADMIN.")
    except Exception as e:
        print(f"Error creating/updating superuser {username}: {e}")
