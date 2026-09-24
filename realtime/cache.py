"""
Centralized Redis helper for Rovexa real-time features with automatic in-memory fallback.
Prevents ConnectionError crashes when Redis is offline.
"""

import json
import logging
import redis
from django.conf import settings

logger = logging.getLogger(__name__)
_client = None


class MemoryFallback:
    """In-memory dictionary fallback when Redis server is offline."""
    def __init__(self):
        self.store = {}
        self.sets = {}

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        return True

    def setex(self, key, ttl, value):
        self.store[key] = str(value)

    def get(self, key):
        return self.store.get(key)

    def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)
            self.sets.pop(k, None)

    def sadd(self, name, *values):
        if name not in self.sets:
            self.sets[name] = set()
        for v in values:
            self.sets[name].add(str(v))

    def srem(self, name, *values):
        if name in self.sets:
            for v in values:
                self.sets[name].discard(str(v))

    def smembers(self, name):
        return self.sets.get(name, set())

    def geoadd(self, name, values):
        pass

    def zrem(self, name, *values):
        pass

    def geosearch(self, *args, **kwargs):
        return []

    def scan_iter(self, match="*"):
        return []

    def ping(self):
        return True


_memory_fallback = MemoryFallback()


def get_redis():
    global _client
    if _client is None:
        try:
            client = redis.from_url(
                getattr(settings, "REDIS_URL", "redis://127.0.0.1:6379"),
                decode_responses=True,
                socket_connect_timeout=1,
            )
            client.ping()
            _client = client
        except Exception:
            _client = _memory_fallback
    return _client


class DriverLocationCache:
    """
    Stores driver GPS in Redis for ultra-fast geospatial lookups.
    Falls back to in-memory fallback if Redis is unreachable.
    """

    LOCATION_TTL = 30
    ONLINE_SET   = "drivers:online"

    def set_location(self, driver_id: str, lat: float, lng: float,
                     heading: float = 0, speed: float = 0, socket_channel: str = ""):
        try:
            r = get_redis()
            key = f"driver:location:{driver_id}"
            payload = {
                "driver_id":      driver_id,
                "lat":            lat,
                "lng":            lng,
                "heading":        heading,
                "speed":          speed,
                "socket_channel": socket_channel,
            }
            r.setex(key, self.LOCATION_TTL, json.dumps(payload))
            try:
                r.geoadd("drivers:geo", (lng, lat, driver_id))
            except Exception:
                pass
            r.sadd(self.ONLINE_SET, driver_id)
        except Exception as e:
            logger.warning(f"[DriverLocationCache.set_location] {e}")

    def get_location(self, driver_id: str) -> dict | None:
        try:
            r = get_redis()
            raw = r.get(f"driver:location:{driver_id}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def get_driver_location(self, driver_id: str) -> dict | None:
        return self.get_location(driver_id)

    def set_offline(self, driver_id: str):
        try:
            r = get_redis()
            r.delete(f"driver:location:{driver_id}")
            r.srem(self.ONLINE_SET, driver_id)
            try:
                r.zrem("drivers:geo", driver_id)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[DriverLocationCache.set_offline] {e}")

    def get_online_driver_ids(self) -> list:
        try:
            r = get_redis()
            return list(r.smembers(self.ONLINE_SET))
        except Exception:
            return []

    def find_nearby_drivers(self, lat: float, lng: float, radius_km: float) -> list:
        try:
            r = get_redis()
            results = r.geosearch(
                "drivers:geo",
                longitude=lng,
                latitude=lat,
                radius=radius_km,
                unit="km",
                sort="ASC",
                withcoord=True,
                withdist=True,
            )
            nearby = []
            for item in results:
                driver_id  = item[0]
                distance   = round(float(item[1]), 2)
                coords     = item[2]
                location   = self.get_location(driver_id) or {}
                nearby.append({
                    "driver_id":   driver_id,
                    "distance_km": distance,
                    "lat":         coords[1],
                    "lng":         coords[0],
                    "heading":     location.get("heading", 0),
                    "speed":       location.get("speed", 0),
                    "channel":     location.get("socket_channel", ""),
                })
            return nearby
        except Exception:
            return []


class BookingLockCache:
    """
    Distributed lock to prevent multiple drivers accepting the same booking.
    """

    LOCK_TTL = 20

    def acquire_lock(self, booking_id: str, driver_id: str) -> bool:
        try:
            r = get_redis()
            key = f"booking:lock:{booking_id}"
            result = r.set(key, driver_id, ex=self.LOCK_TTL, nx=True)
            return result is True
        except Exception:
            return True

    def release_lock(self, booking_id: str):
        try:
            r = get_redis()
            r.delete(f"booking:lock:{booking_id}")
        except Exception:
            pass

    def get_lock_holder(self, booking_id: str) -> str | None:
        try:
            r = get_redis()
            return r.get(f"booking:lock:{booking_id}")
        except Exception:
            return None


class RideRequestCache:
    """
    Tracks which drivers were sent a ride request, and their response status.
    """

    TTL = 60

    def set_pending_drivers(self, booking_id: str, driver_ids: list):
        try:
            r = get_redis()
            key = f"ride_request:{booking_id}:drivers"
            r.setex(key, self.TTL, json.dumps(driver_ids))
        except Exception:
            pass

    def get_pending_drivers(self, booking_id: str) -> list:
        try:
            r = get_redis()
            raw = r.get(f"ride_request:{booking_id}:drivers")
            return json.loads(raw) if raw else []
        except Exception:
            return []

    def set_driver_response(self, booking_id: str, driver_id: str, response: str):
        try:
            r = get_redis()
            r.setex(f"ride_request:{booking_id}:resp:{driver_id}", 60, response)
        except Exception:
            pass

    def clear(self, booking_id: str):
        try:
            r = get_redis()
            for key in r.scan_iter(f"ride_request:{booking_id}:*"):
                r.delete(key)
        except Exception:
            pass


# Singletons
driver_location_cache = DriverLocationCache()
booking_lock_cache    = BookingLockCache()
ride_request_cache    = RideRequestCache()
