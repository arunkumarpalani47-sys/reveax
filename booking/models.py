import random
from decimal import Decimal
from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from vehicle.models import Vehicle


class PricingRule(models.Model):
    vehicle_type = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    base_fare = models.DecimalField(max_digits=10, decimal_places=2, default=40)
    rate_per_km = models.DecimalField(max_digits=10, decimal_places=2, default=15)
    rate_per_min = models.DecimalField(max_digits=10, decimal_places=2, default=2)
    night_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    airport_flat_charge = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    surge_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name} ({self.vehicle_type}) - ₹{self.rate_per_km}/km [Surge {self.surge_multiplier}x]"


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    min_trip_fare = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    uses_count = models.IntegerField(default=0)
    max_uses = models.IntegerField(default=1000)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({self.discount_percent}% off up to ₹{self.max_discount_amount})"


class Booking(models.Model):

    STATUS_CHOICES = (
        ("PENDING",       "Pending Admin Review"),
        ("ACCEPTED",      "Accepted by Admin"),
        ("REJECTED",      "Rejected by Admin"),
        ("TRIP_STARTED",  "Trip Started"),
        ("TRIP_COMPLETED", "Trip Completed"),
        ("CANCELLED",     "Cancelled"),
    )

    customer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="customer_bookings"
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    driver = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_bookings"
    )

    pickup_location = models.CharField(max_length=255)
    drop_location   = models.CharField(max_length=255)

    pickup_lat = models.FloatField(null=True, blank=True)
    pickup_lng = models.FloatField(null=True, blank=True)
    drop_lat   = models.FloatField(null=True, blank=True)
    drop_lng   = models.FloatField(null=True, blank=True)

    booking_date = models.DateField(auto_now_add=True)
    booking_time = models.TimeField(auto_now_add=True)

    distance = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0
    )

    total_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # Dynamic Fare Breakdown Fields
    base_fare_component    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    distance_fare_component= models.DecimalField(max_digits=10, decimal_places=2, default=0)
    time_fare_component    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    surge_multiplier       = models.DecimalField(max_digits=4,  decimal_places=2, default=1.0)
    night_charge           = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    airport_charge         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount        = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code            = models.CharField(max_length=50, blank=True, default="")

    VEHICLE_TYPES = (
        ("CAR_CAB", "Rovexa Car Cab (4+ Seats)"),
        ("AUTO", "Auto Rickshaw"),
        ("MINI", "Mini / Hatchback"),
        ("SEDAN", "Prime Sedan"),
        ("SUV", "Suv / Innova"),
        ("LUXURY", "Luxury"),
        ("PREMIUM", "Premium"),
    )

    PAYMENT_METHODS = (
        ("CASH",   "Cash Payment"),
        ("WALLET", "Rovexa Wallet"),
        ("ONLINE", "Online Payment / UPI"),
    )

    vehicle_type = models.CharField(max_length=50, choices=VEHICLE_TYPES, default="MINI")
    estimated_duration = models.IntegerField(default=0)  # minutes

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    otp = models.CharField(max_length=6, blank=True, default="")
    otp_verified = models.BooleanField(default=False)

    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHODS, default="CASH")
    payment_status = models.CharField(max_length=30, default="PENDING")

    # Customer Rating & Feedback
    rating = models.PositiveIntegerField(null=True, blank=True)
    review_comment = models.TextField(blank=True, default="")
    rating_date = models.DateTimeField(null=True, blank=True)

    # Sprint 7 Safety & Public Share Token
    share_token = models.CharField(max_length=100, blank=True, default="")

    # Sprint 8 Advanced Ride Types (Book Later, Rentals, Outstation)
    BOOKING_CATEGORIES = (
        ("DAILY_RIDE", "Daily Ride"),
        ("SCHEDULED",  "Book Later (Scheduled)"),
        ("RENTAL",     "Hourly Rental"),
        ("OUTSTATION", "Outstation Cab"),
    )

    booking_category = models.CharField(
        max_length=30,
        choices=BOOKING_CATEGORIES,
        default="DAILY_RIDE"
    )
    scheduled_datetime = models.DateTimeField(null=True, blank=True)
    passenger_name     = models.CharField(max_length=100, blank=True, default="")
    passenger_phone    = models.CharField(max_length=20, blank=True, default="")
    driver_notes       = models.TextField(blank=True, default="")
    rental_package     = models.CharField(max_length=50, blank=True, default="")
    outstation_type    = models.CharField(max_length=20, blank=True, default="ONE_WAY")
    TRIP_TYPE_CHOICES = (
        ("ONE_WAY", "One Way"),
        ("ROUND_TRIP", "Round Trip"),
    )
    trip_type = models.CharField(
        max_length=20,
        choices=TRIP_TYPE_CHOICES,
        default="ONE_WAY"
    )
    return_datetime    = models.DateTimeField(null=True, blank=True)

    waypoints_json = models.TextField(blank=True, default="[]")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def safe_customer_name(self):
        if self.passenger_name:
            return self.passenger_name
        try:
            if self.customer:
                full_name = self.customer.get_full_name()
                return full_name if full_name.strip() else self.customer.username
        except Exception:
            pass
        return "Passenger"

    @property
    def safe_customer_phone(self):
        if self.passenger_phone:
            return self.passenger_phone
        try:
            if self.customer and getattr(self.customer, "phone", None):
                return self.customer.phone
        except Exception:
            pass
        return "+91 9876543210"

    @property
    def safe_vehicle_name(self):
        try:
            if self.vehicle and getattr(self.vehicle, "vehicle_name", None):
                return self.vehicle.vehicle_name
        except Exception:
            pass
        return self.get_vehicle_type_display() if hasattr(self, "get_vehicle_type_display") else (self.vehicle_type or "Standard Cab")

    @property
    def safe_vehicle_number(self):
        try:
            if self.vehicle and getattr(self.vehicle, "vehicle_number", None):
                return self.vehicle.vehicle_number
        except Exception:
            pass
        return "TN-01-AX-1234"

    def save(self, *args, **kwargs):
        import uuid
        if not self.otp:
            self.otp = f"{random.randint(100000, 999999)}"
        if not self.share_token:
            self.share_token = f"TRACK_{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking #{self.id} ({self.status})"



class EmergencyAlert(models.Model):
    STATUS_CHOICES = (
        ("ACTIVE", "Active SOS Alert"),
        ("RESOLVED", "Resolved / Dismissed"),
    )

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="sos_alerts"
    )
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sos_triggers"
    )
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    current_address = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"🚨 SOS Alert #{self.id} for Booking #{self.booking.id} [{self.status}]"


class FareSplit(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending Approval"),
        ("ACCEPTED", "Accepted & Paid"),
        ("REJECTED", "Rejected"),
    )

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="fare_splits"
    )
    requester = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="requested_splits"
    )
    participant_email = models.EmailField()
    split_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Split #{self.id} for Booking #{self.booking.id} - ₹{self.split_amount} [{self.status}]"





class RideChatMessage(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="chat_messages")
    sender = models.CharField(max_length=20, default="CUSTOMER")
    sender_name = models.CharField(max_length=100, default="User")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.sender}] Booking #{self.booking.id}: {self.message[:30]}"