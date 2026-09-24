from decimal import Decimal
from django.test import TestCase
from accounts.models import CustomUser
from booking.models import Booking, Coupon
from booking.pricing import get_real_road_distance, calculate_trip_fare
from booking.forms import BookingForm

class PricingEngineTests(TestCase):
    def test_road_distance_calculation(self):
        """Test Haversine/OSRM road distance algorithm returns positive distance."""
        dist = get_real_road_distance(12.9716, 77.5946, 12.9352, 77.6245)
        self.assertGreater(dist, 0.0)
        self.assertIsInstance(dist, float)

    def test_trip_fare_calculation_structure(self):
        """Test trip fare calculation returns complete breakdown fields."""
        fare = calculate_trip_fare(
            vehicle_type="SEDAN",
            distance_km=10.0,
            duration_mins=20,
            pickup_address="Kanchipuram",
            drop_address="Chennai Airport",
            booking_category="DAILY_RIDE"
        )
        self.assertIn("total_fare", fare)
        self.assertIn("base_fare", fare)
        self.assertIn("distance_fare", fare)
        self.assertGreater(fare["total_fare"], 0)

    def test_coupon_model_creation(self):
        """Test coupon model creation and properties."""
        coupon = Coupon.objects.create(
            code="WELCOME2026",
            discount_percent=Decimal("15.00"),
            max_discount_amount=Decimal("100.00"),
            min_trip_fare=Decimal("100.00"),
            is_active=True
        )
        self.assertEqual(coupon.code, "WELCOME2026")
        self.assertEqual(coupon.discount_percent, Decimal("15.00"))
        self.assertTrue(coupon.is_active)

class BookingFormValidationTests(TestCase):
    def test_valid_booking_form(self):
        """Test BookingForm with valid fields."""
        form = BookingForm(data={
            "booking_category": "DAILY_RIDE",
            "vehicle_type": "MINI",
            "payment_method": "CASH"
        })
        self.assertTrue(form.is_valid())

    def test_invalid_vehicle_type(self):
        """Test BookingForm rejects unknown vehicle types."""
        form = BookingForm(data={
            "booking_category": "DAILY_RIDE",
            "vehicle_type": "SUBMARINE",
            "payment_method": "CASH"
        })
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_type", form.errors)
