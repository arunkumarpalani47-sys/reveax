from decimal import Decimal
from django.test import TestCase
from accounts.models import CustomUser
from vehicle.models import Vehicle

class VehicleModelTests(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            username="fleet_partner",
            password="Password123!",
            role="PARTNER"
        )

    def test_create_vehicle_record(self):
        """Test creating a vehicle inventory record."""
        vehicle = Vehicle.objects.create(
            owner=self.owner,
            vehicle_name="Swift Dzire",
            brand="Maruti",
            model="2024",
            vehicle_number="TN01AB1234",
            vehicle_type="SEDAN",
            fuel_type="PETROL",
            seats=4,
            price_per_km=Decimal("15.00"),
            is_available=True
        )
        self.assertEqual(vehicle.vehicle_type, "SEDAN")
        self.assertTrue(vehicle.is_available)
        self.assertEqual(vehicle.price_per_km, Decimal("15.00"))
