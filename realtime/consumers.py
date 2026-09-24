"""
WebSocket Consumers for Rovexa Real-Time Engine.

Four consumers:
  1. LocationConsumer    — Driver sends GPS every 3s → stored in Redis → broadcast to customer
  2. BookingConsumer     — Customer listens for ride status changes
  3. DriverConsumer      — Driver receives ride requests, can go online/offline
  4. RideRequestConsumer — Handles the 15-second accept/reject flow
"""

import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .cache import driver_location_cache, booking_lock_cache, ride_request_cache

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LOCATION CONSUMER  —  ws/location/
#    Driver connects and sends GPS pings every 3 seconds.
# ═══════════════════════════════════════════════════════════════════════════════

class LocationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.user = self.scope["user"]
        self.driver_id = str(self.user.id)
        self.driver_group = f"driver_{self.driver_id}"

        # Join driver-specific group
        await self.channel_layer.group_add(self.driver_group, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "Location stream connected. Send GPS pings every 3 seconds.",
            "driver_id": self.driver_id,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "driver_id"):
            # Mark driver offline in Redis
            await asyncio.get_event_loop().run_in_executor(
                None, driver_location_cache.set_offline, self.driver_id
            )
            await self.channel_layer.group_discard(self.driver_group, self.channel_name)
            # Notify admin group driver went offline
            await self.channel_layer.group_send("admin_operations", {
                "type":      "driver.offline",
                "driver_id": self.driver_id,
            })

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type")

            if msg_type == "gps_update":
                await self._handle_gps(data)
            elif msg_type == "go_online":
                await self._handle_online()
            elif msg_type == "go_offline":
                await self._handle_offline()

        except (json.JSONDecodeError, KeyError) as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def _handle_gps(self, data: dict):
        lat     = float(data.get("lat", 0))
        lng     = float(data.get("lng", 0))
        heading = float(data.get("heading", 0))
        speed   = float(data.get("speed", 0))

        # Store in Redis (non-blocking)
        await asyncio.get_event_loop().run_in_executor(
            None,
            driver_location_cache.set_location,
            self.driver_id, lat, lng, heading, speed, self.channel_name
        )

        # Update DB location (non-blocking)
        await self._update_db_location(lat, lng, heading, speed)

        # Broadcast to admin operations room (live map)
        await self.channel_layer.group_send("admin_operations", {
            "type":      "driver.location",
            "driver_id": self.driver_id,
            "lat":       lat,
            "lng":       lng,
            "heading":   heading,
            "speed":     speed,
        })

        # If driver is on a trip, broadcast to customer
        booking_id = await self._get_active_booking_id()
        if booking_id:
            await self.channel_layer.group_send(f"booking_{booking_id}", {
                "type":      "driver.location",
                "driver_id": self.driver_id,
                "lat":       lat,
                "lng":       lng,
                "heading":   heading,
                "speed":     speed,
            })

        await self.send(text_data=json.dumps({"type": "gps_ack", "lat": lat, "lng": lng}))

    async def _handle_online(self):
        await self._set_driver_available(True)
        await self.send(text_data=json.dumps({"type": "status", "online": True}))

    async def _handle_offline(self):
        await asyncio.get_event_loop().run_in_executor(
            None, driver_location_cache.set_offline, self.driver_id
        )
        await self._set_driver_available(False)
        await self.send(text_data=json.dumps({"type": "status", "online": False}))

    @database_sync_to_async
    def _update_db_location(self, lat, lng, heading, speed):
        try:
            from realtime.models import DriverLocation
            DriverLocation.objects.update_or_create(
                driver_id=self.driver_id,
                defaults={
                    "lat":      lat,
                    "lng":      lng,
                    "heading":  heading,
                    "speed":    speed,
                    "last_seen": timezone.now(),
                    "is_online": True,
                }
            )
        except Exception as e:
            logger.warning(f"DB location update failed: {e}")

    @database_sync_to_async
    def _set_driver_available(self, is_available: bool):
        try:
            from realtime.models import DriverLocation
            DriverLocation.objects.update_or_create(
                driver_id=self.driver_id,
                defaults={"is_online": is_available, "last_seen": timezone.now()}
            )
        except Exception:
            pass

    @database_sync_to_async
    def _get_active_booking_id(self):
        try:
            from booking.models import Booking
            b = Booking.objects.filter(
                driver_id=self.driver_id,
                status__in=["DRIVER_COMING", "DRIVER_ARRIVED", "TRIP_STARTED"]
            ).first()
            return str(b.id) if b else None
        except Exception:
            return None

    # Group message handler
    async def driver_location(self, event):
        await self.send(text_data=json.dumps(event))

    async def driver_offline(self, event):
        await self.send(text_data=json.dumps(event))


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BOOKING CONSUMER  —  ws/booking/<booking_id>/
#    Customer connects to listen for their ride status updates.
# ═══════════════════════════════════════════════════════════════════════════════

class BookingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.booking_id   = self.scope["url_route"]["kwargs"]["booking_id"]
        self.booking_group = f"booking_{self.booking_id}"

        await self.channel_layer.group_add(self.booking_group, self.channel_name)
        await self.accept()

        # Send current booking status immediately
        status = await self._get_booking_status()
        await self.send(text_data=json.dumps({
            "type":       "booking_status",
            "booking_id": self.booking_id,
            "status":     status,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "booking_group"):
            await self.channel_layer.group_discard(self.booking_group, self.channel_name)

    async def receive(self, text_data):
        pass   # Customer side is read-only

    # ─── Group message handlers ────────────────────────────────────────────────
    async def booking_status(self, event):
        await self.send(text_data=json.dumps(event))

    async def driver_location(self, event):
        await self.send(text_data=json.dumps(event))

    async def booking_cancelled(self, event):
        await self.send(text_data=json.dumps(event))

    async def driver_arrived(self, event):
        await self.send(text_data=json.dumps(event))

    async def trip_started(self, event):
        await self.send(text_data=json.dumps(event))

    async def trip_completed(self, event):
        await self.send(text_data=json.dumps(event))

    async def payment_required(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _get_booking_status(self):
        try:
            from booking.models import Booking
            b = Booking.objects.get(id=self.booking_id)
            return b.status
        except Exception:
            return "NOT_FOUND"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. DRIVER CONSUMER  —  ws/driver/
#    Driver connects to receive ride requests and manage availability.
# ═══════════════════════════════════════════════════════════════════════════════

class DriverConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.user      = self.scope["user"]
        self.driver_id = str(self.user.id)
        self.group     = f"driver_requests_{self.driver_id}"

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            "type":    "connected",
            "message": "Driver channel active. Waiting for ride requests.",
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data):
        try:
            data     = json.loads(text_data)
            msg_type = data.get("type")

            if msg_type == "accept_ride":
                await self._handle_accept(data.get("booking_id"))
            elif msg_type == "reject_ride":
                await self._handle_reject(data.get("booking_id"))

        except (json.JSONDecodeError, KeyError) as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def _handle_accept(self, booking_id: str):
        if not booking_id:
            return

        # Try to acquire distributed Redis lock
        acquired = await asyncio.get_event_loop().run_in_executor(
            None, booking_lock_cache.acquire_lock, booking_id, self.driver_id
        )

        if acquired:
            # Lock acquired — assign this driver to booking
            await self._assign_driver(booking_id)
            await self.send(text_data=json.dumps({
                "type":       "ride_accepted",
                "booking_id": booking_id,
                "message":    "Ride assigned to you! Navigate to pickup.",
            }))
            # Cancel the other pending drivers
            await self._cancel_other_drivers(booking_id)
            # Notify customer
            await self.channel_layer.group_send(f"booking_{booking_id}", {
                "type":      "booking_status",
                "booking_id": booking_id,
                "status":    "DRIVER_ASSIGNED",
                "driver_id": self.driver_id,
            })
        else:
            # Another driver got it first
            await self.send(text_data=json.dumps({
                "type":    "ride_taken",
                "message": "This ride was just accepted by another driver.",
            }))

    async def _handle_reject(self, booking_id: str):
        await self.send(text_data=json.dumps({
            "type":    "ride_rejected",
            "booking_id": booking_id,
        }))
        # Record rejection in Redis so booking service knows
        await asyncio.get_event_loop().run_in_executor(
            None, ride_request_cache.set_driver_response, booking_id, self.driver_id, "REJECTED"
        )

    @database_sync_to_async
    def _assign_driver(self, booking_id: str):
        from booking.models import Booking
        Booking.objects.filter(id=booking_id).update(
            driver_id=self.driver_id,
            status="DRIVER_ASSIGNED"
        )

    async def _cancel_other_drivers(self, booking_id: str):
        pending_drivers = await asyncio.get_event_loop().run_in_executor(
            None, ride_request_cache.get_pending_drivers, booking_id
        )
        for did in pending_drivers:
            if did != self.driver_id:
                await self.channel_layer.group_send(f"driver_requests_{did}", {
                    "type":       "ride_cancelled",
                    "booking_id": booking_id,
                    "reason":     "Ride was accepted by another driver.",
                })

    # ─── Group message handlers ────────────────────────────────────────────────
    async def ride_request(self, event):
        """Receive incoming ride request from booking service."""
        await self.send(text_data=json.dumps(event))

    async def ride_cancelled(self, event):
        await self.send(text_data=json.dumps(event))

    async def driver_location(self, event):
        await self.send(text_data=json.dumps(event))


# ═══════════════════════════════════════════════════════════════════════════════
# 4. RIDE REQUEST CONSUMER  —  ws/ride-request/<booking_id>/
#    Admin / system view of a specific ride request broadcast.
# ═══════════════════════════════════════════════════════════════════════════════

class RideRequestConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.booking_id = self.scope["url_route"]["kwargs"]["booking_id"]
        self.group      = f"ride_request_{self.booking_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data):
        pass

    async def ride_update(self, event):
        await self.send(text_data=json.dumps(event))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. WALLET CONSUMER  —  ws/wallet/
#    Real-time banking balance & passbook updates stream.
# ═══════════════════════════════════════════════════════════════════════════════

class WalletConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if user and hasattr(user, "is_authenticated") and user.is_authenticated:
            self.user_id = str(user.id)
        else:
            self.user_id = "general"

        self.wallet_group = f"wallet_{self.user_id}"

        await self.channel_layer.group_add(self.wallet_group, self.channel_name)
        await self.channel_layer.group_add("wallet_broadcast", self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "Real-time banking wallet stream connected.",
            "user_id": self.user_id,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "wallet_group"):
            await self.channel_layer.group_discard(self.wallet_group, self.channel_name)

    async def receive(self, text_data):
        pass

    async def wallet_update(self, event):
        """Handler called when wallet update is broadcast."""
        await self.send(text_data=json.dumps(event))

