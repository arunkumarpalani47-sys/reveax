"""
Realtime API views — REST endpoints called by the frontend JS.
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings

from .cache import driver_location_cache, ride_request_cache
from .booking_service import find_and_notify_drivers, broadcast_booking_status, log_ride_event

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def api_nearby_drivers(request):
    """
    GET /realtime/api/nearby-drivers/?lat=&lng=&radius=
    Returns list of nearby online drivers from Redis.
    """
    try:
        lat       = float(request.GET.get("lat", 0))
        lng       = float(request.GET.get("lng", 0))
        radius_km = float(request.GET.get("radius", 2))
        drivers   = driver_location_cache.find_nearby_drivers(lat, lng, radius_km)
        return JsonResponse({"success": True, "drivers": drivers, "count": len(drivers)})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_driver_toggle(request):
    """
    POST /realtime/api/driver/toggle/
    Body: {"online": true}
    Toggle driver online/offline status.
    """
    try:
        data      = json.loads(request.body)
        driver_id = str(request.user.id)
        is_online = bool(data.get("online", False))

        if is_online:
            lat = float(data.get("lat", 0))
            lng = float(data.get("lng", 0))
            driver_location_cache.set_location(driver_id, lat, lng)
            msg = "You are now ONLINE"
        else:
            driver_location_cache.set_offline(driver_id)
            msg = "You are now OFFLINE"

        log_ride_event(
            booking_id="N/A",
            event_type="DRIVER_SEARCH" if is_online else "BOOKING_CANCELLED",
            actor_id=driver_id,
            actor_role="DRIVER",
            meta={"online": is_online},
        )
        return JsonResponse({"success": True, "online": is_online, "message": msg})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_search_driver(request):
    """
    POST /realtime/api/search-driver/
    Body: {"booking_id": "...", "lat": ..., "lng": ..., "vehicle_type": "...", "fare": ..., "distance_km": ...}
    Triggers geospatial driver search and sends ride requests.
    """
    try:
        data        = json.loads(request.body)
        booking_id  = data["booking_id"]
        lat         = float(data["lat"])
        lng         = float(data["lng"])
        vehicle     = data.get("vehicle_type", "MINI")
        fare        = float(data.get("fare", 0))
        distance_km = float(data.get("distance_km", 0))

        driver_ids = find_and_notify_drivers(
            booking_id, lat, lng, vehicle, fare, distance_km
        )
        log_ride_event(booking_id, "DRIVER_SEARCH", actor_id=str(request.user.id),
                       actor_role="SYSTEM", lat=lat, lng=lng,
                       meta={"notified_drivers": driver_ids})

        if driver_ids:
            return JsonResponse({
                "success":         True,
                "drivers_notified": len(driver_ids),
                "message":         f"Ride request sent to {len(driver_ids)} driver(s)",
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "No drivers available nearby. Please try again in a few minutes.",
            }, status=200)

    except Exception as e:
        logger.error(f"[api_search_driver] {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_booking_status_update(request):
    """
    POST /realtime/api/booking/status/
    Body: {"booking_id": "...", "status": "DRIVER_ARRIVED"}
    Called internally to push status to customer WebSocket.
    """
    try:
        data       = json.loads(request.body)
        booking_id = data["booking_id"]
        status     = data["status"]
        extra      = data.get("extra", {})

        broadcast_booking_status(booking_id, status, extra)
        log_ride_event(booking_id, status, actor_id=str(request.user.id), actor_role="DRIVER")

        return JsonResponse({"success": True, "status_broadcast": status})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_online_drivers_count(request):
    """GET /realtime/api/online-drivers/count/ — for admin dashboard."""
    ids   = driver_location_cache.get_online_driver_ids()
    count = len(ids)
    return JsonResponse({"success": True, "online_count": count, "driver_ids": ids})
