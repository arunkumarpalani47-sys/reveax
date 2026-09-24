"""
Booking service for Rovexa — handles driver search, assignment, and status transitions.
Called from booking views and WebSocket consumers.
"""

import asyncio
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings

from .cache import driver_location_cache, booking_lock_cache, ride_request_cache

logger = logging.getLogger(__name__)

channel_layer = get_channel_layer()


def find_and_notify_drivers(booking_id: str, lat: float, lng: float,
                             vehicle_type: str, fare: float, distance_km: float):
    return []


def broadcast_booking_status(booking_id: str, status: str, extra: dict = None):
    """
    Broadcast status update to the booking's WebSocket group (customer listens here).
    """
    payload = {
        "type":       "booking_status",
        "booking_id": str(booking_id),
        "status":     status,
    }
    if extra:
        payload.update(extra)
    try:
        async_to_sync(channel_layer.group_send)(f"booking_{booking_id}", payload)
    except Exception as e:
        logger.warning(f"[BookingService] Broadcast failed for {booking_id}: {e}")


def _mark_no_driver(booking_id: str):
    """Update booking status in DB to NO_DRIVER_FOUND."""
    try:
        from booking.models import Booking
        Booking.objects.filter(id=booking_id).update(status="NO_DRIVER_FOUND")
        broadcast_booking_status(booking_id, "NO_DRIVER_FOUND")
    except Exception as e:
        logger.error(f"[BookingService] Could not mark no-driver: {e}")


def log_ride_event(booking_id: str, event_type: str, actor_id: str = "",
                   actor_role: str = "SYSTEM", lat=None, lng=None, meta: dict = None):
    """Write an immutable ride log entry."""
    try:
        from realtime.models import RideLog
        RideLog.objects.create(
            booking_id=str(booking_id),
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            lat=lat,
            lng=lng,
            metadata=meta or {},
        )
    except Exception as e:
        logger.warning(f"[RideLog] Could not write log: {e}")
