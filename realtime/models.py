"""
Database models for realtime engine.
"""

from django.db import models
from django.utils import timezone


class DriverLocation(models.Model):
    """
    Persists the last known driver location in the database.
    Redis stores the active (fast) version; this is the durable backup.
    """
    driver_id  = models.CharField(max_length=100, unique=True, db_index=True)
    lat        = models.FloatField(default=0.0)
    lng        = models.FloatField(default=0.0)
    heading    = models.FloatField(default=0.0)   # degrees 0-360
    speed      = models.FloatField(default=0.0)   # km/h
    is_online  = models.BooleanField(default=False)
    last_seen  = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name        = "Driver Location"
        verbose_name_plural = "Driver Locations"
        ordering            = ["-last_seen"]

    def __str__(self):
        return f"Driver {self.driver_id} @ ({self.lat:.4f}, {self.lng:.4f})"


class RideLog(models.Model):
    """
    Immutable event log for every state change in a booking.
    Useful for dispute resolution and analytics.
    """
    EVENT_CHOICES = [
        ("BOOKING_CREATED",   "Booking Created"),
        ("DRIVER_SEARCH",     "Searching Driver"),
        ("DRIVER_ASSIGNED",   "Driver Assigned"),
        ("DRIVER_COMING",     "Driver En Route"),
        ("DRIVER_ARRIVED",    "Driver Arrived"),
        ("OTP_VERIFIED",      "OTP Verified"),
        ("TRIP_STARTED",      "Trip Started"),
        ("TRIP_COMPLETED",    "Trip Completed"),
        ("BOOKING_CANCELLED", "Booking Cancelled"),
        ("PAYMENT_DONE",      "Payment Done"),
        ("DRIVER_REJECTED",   "Driver Rejected Ride"),
        ("TIMEOUT",           "Request Timed Out"),
    ]

    booking_id  = models.CharField(max_length=100, db_index=True)
    event_type  = models.CharField(max_length=30, choices=EVENT_CHOICES)
    actor_id    = models.CharField(max_length=100, blank=True)   # user/driver who triggered
    actor_role  = models.CharField(max_length=20, blank=True)    # CUSTOMER / DRIVER / SYSTEM
    lat         = models.FloatField(null=True, blank=True)        # location when event happened
    lng         = models.FloatField(null=True, blank=True)
    metadata    = models.JSONField(default=dict, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Ride Log"
        verbose_name_plural = "Ride Logs"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"[{self.event_type}] Booking {self.booking_id}"
