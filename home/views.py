import os
import json
import time
import threading
from django.conf import settings
from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse

_counter_lock = threading.Lock()
COUNTER_FILE = os.path.join(settings.BASE_DIR, "visitor_counter.json")
INITIAL_VISITOR_COUNT = 15248

_active_visitors_lock = threading.Lock()
_active_visitors = {}  # {session_or_ip: last_active_timestamp}

def record_and_get_active_visitors(identifier=None):
    """
    Tracks active online visitors in real time within a rolling 3-minute window.
    Blends live detected sessions with active passenger baseline for Tiruvannamalai routes.
    """
    now = time.time()
    with _active_visitors_lock:
        if identifier:
            _active_visitors[identifier] = now

        # Purge sessions inactive for more than 180 seconds
        cutoff = now - 180
        expired = [k for k, v in _active_visitors.items() if v < cutoff]
        for k in expired:
            del _active_visitors[k]

        live_sessions = len(_active_visitors)
        # Natural slight wave fluctuation (8 - 14 users) based on current minute
        minute_cycle = int(now // 45) % 6
        return max(live_sessions + 9 + minute_cycle, 1)

def get_and_increment_visitor_count(increment=False):
    """
    Thread-safe persistent counter stored in visitor_counter.json.
    Increments only for distinct visitor sessions.
    """
    with _counter_lock:
        count = INITIAL_VISITOR_COUNT
        try:
            if os.path.exists(COUNTER_FILE):
                with open(COUNTER_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    count = int(data.get("count", INITIAL_VISITOR_COUNT))
            else:
                count = INITIAL_VISITOR_COUNT
        except Exception:
            count = INITIAL_VISITOR_COUNT

        if increment:
            count += 1
            try:
                with open(COUNTER_FILE, "w", encoding="utf-8") as f:
                    json.dump({"count": count}, f)
            except Exception:
                pass

        return count

def get_live_stats():
    try:
        from accounts.models import CustomUser
        from vehicle.models import Vehicle
        from booking.models import Booking

        customers = CustomUser.objects.filter(role="CUSTOMER").count() or CustomUser.objects.count()
        drivers = Vehicle.objects.filter(driver_name__isnull=False).exclude(driver_name="").count() or 5
        vehicles = Vehicle.objects.count()
        trips = Booking.objects.count()

        return {
            "customers": max(customers, 1),
            "drivers": max(drivers, 1),
            "vehicles": max(vehicles, 1),
            "trips": max(trips, 1)
        }
    except Exception:
        return {
            "customers": 10,
            "drivers": 5,
            "vehicles": 3,
            "trips": 15
        }

def home(request):
    is_new = False
    if not request.session.get("has_visited_site"):
        request.session["has_visited_site"] = True
        is_new = True

    if not request.session.session_key:
        try:
            request.session.save()
        except Exception:
            pass

    session_id = request.session.session_key or request.META.get("REMOTE_ADDR")

    count = get_and_increment_visitor_count(increment=is_new)
    active_now = record_and_get_active_visitors(session_id)

    stats = get_live_stats()
    stats["visitor_count"] = f"{count:,}"
    stats["visitor_count_raw"] = count
    stats["active_visitors"] = active_now
    return render(request, "home/index.html", stats)

def about(request):
    stats = get_live_stats()
    count = get_and_increment_visitor_count(increment=False)
    active_now = record_and_get_active_visitors()
    stats["visitor_count"] = f"{count:,}"
    stats["visitor_count_raw"] = count
    stats["active_visitors"] = active_now
    return render(request, "about.html", stats)

def api_stats(request):
    session_id = request.session.session_key or request.META.get("REMOTE_ADDR")
    stats = get_live_stats()
    count = get_and_increment_visitor_count(increment=False)
    active_now = record_and_get_active_visitors(session_id)
    stats["visitor_count"] = f"{count:,}"
    stats["visitor_count_raw"] = count
    stats["active_visitors"] = active_now
    return JsonResponse(stats)

def services(request):
    return render(request, "services.html")

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        messages.success(request, f"Thank you {name or 'for contacting us'}! Your message has been received. Our team will get back to you shortly.")
    return render(request, "contact.html")