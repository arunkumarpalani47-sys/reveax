from django.test import TestCase
from accounts.models import CustomUser

class UserAccountTests(TestCase):
    def test_create_customer_user(self):
        """Test creating a customer user account."""
        user = CustomUser.objects.create_user(
            username="customer_test",
            email="customer@example.com",
            password="Password123!",
            role="CUSTOMER",
            phone="9876543210"
        )
        self.assertEqual(user.role, "CUSTOMER")
        self.assertEqual(user.phone, "9876543210")
        self.assertTrue(user.check_password("Password123!"))

    def test_user_display_name_fallback(self):
        """Test display_name property falls back to username/formatted name."""
        user = CustomUser.objects.create_user(
            username="driver_arun",
            password="Password123!",
            role="DRIVER"
        )
        self.assertIn("Arun", user.display_name)

    def test_user_display_name_full(self):
        """Test display_name property returns full name when available."""
        user = CustomUser.objects.create_user(
            username="partner_arun",
            first_name="Arun",
            last_name="Kumar",
            password="Password123!",
            role="PARTNER"
        )
        self.assertEqual(user.display_name, "Arun Kumar")
