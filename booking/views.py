import csv
from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from vehicle.models import Vehicle
from .models import Booking
from .forms import BookingForm


def is_default_bengaluru(lat_val, lng_val, location_str):
    if not lat_val or not lng_val:
        return True
    try:
        lat_f, lng_f = float(lat_val), float(lng_val)
    except (ValueError, TypeError):
        return True
    if lat_f == 0.0 or lng_f == 0.0:
        return True
    loc_lower = (location_str or "").lower().strip()
    is_exact_default = (
        (abs(lat_f - 12.9716) < 0.005 and abs(lng_f - 77.5946) < 0.005) or
        (abs(lat_f - 12.9352) < 0.005 and abs(lng_f - 77.6245) < 0.005) or
        (abs(lat_f - 12.9600) < 0.005 and abs(lng_f - 77.5800) < 0.005)
    )
    is_in_bengaluru_box = (12.80 <= lat_f <= 13.15) and (77.40 <= lng_f <= 77.80)
    if is_in_bengaluru_box:
        if not any(kw in loc_lower for kw in ["bengaluru", "bangalore", "blr"]):
            return True
        if is_exact_default and len(loc_lower) > 10:
            return True
    return False


def repair_booking_coordinates_and_distance(booking):
    from .pricing import geocode_address_to_lat_lon, get_real_road_distance, calculate_trip_fare

    p_lat = float(booking.pickup_lat) if booking.pickup_lat else 0.0
    p_lng = float(booking.pickup_lng) if booking.pickup_lng else 0.0
    d_lat = float(booking.drop_lat) if booking.drop_lat else 0.0
    d_lng = float(booking.drop_lng) if booking.drop_lng else 0.0

    needs_save = False

    if is_default_bengaluru(p_lat, p_lng, booking.pickup_location):
        g1 = geocode_address_to_lat_lon(booking.pickup_location)
        if g1:
            p_lat, p_lng = g1
            booking.pickup_lat, booking.pickup_lng = p_lat, p_lng
            needs_save = True

    if is_default_bengaluru(d_lat, d_lng, booking.drop_location):
        g2 = geocode_address_to_lat_lon(booking.drop_location)
        if g2:
            d_lat, d_lng = g2
            booking.drop_lat, booking.drop_lng = d_lat, d_lng
            needs_save = True

    road_dist = get_real_road_distance(p_lat, p_lng, d_lat, d_lng, booking.pickup_location, booking.drop_location)
    if road_dist >= 0 and (needs_save or float(booking.distance or 0) <= 0.1 or abs(float(booking.distance or 0) - road_dist) > 0.5):
        booking.distance = Decimal(str(road_dist))
        needs_save = True

    dist_val = float(booking.distance or 0)
    calculated_duration = max(5, int(dist_val * 1.5))
    if not booking.estimated_duration or booking.estimated_duration == 15 or abs(booking.estimated_duration - calculated_duration) > 30:
        booking.estimated_duration = calculated_duration
        needs_save = True

    # Recalculate total_fare if missing, 0, or parameters changed
    if not booking.total_fare or float(booking.total_fare) <= 0 or needs_save:
        # Use vehicle's own price_per_km if available
        vehicle_price_per_km = None
        if booking.vehicle and getattr(booking.vehicle, 'price_per_km', None):
            vehicle_price_per_km = float(booking.vehicle.price_per_km)

        fare_details = calculate_trip_fare(
            vehicle_type=booking.vehicle_type or "MINI",
            distance_km=float(booking.distance),
            duration_mins=booking.estimated_duration,
            pickup_address=booking.pickup_location,
            drop_address=booking.drop_location,
            coupon_code=booking.coupon_code,
            booking_category=booking.booking_category,
            rental_package=booking.rental_package,
            outstation_type=booking.outstation_type,
            vehicle_price_per_km=vehicle_price_per_km,
        )
        booking.total_fare = Decimal(str(fare_details["total_fare"]))
        booking.fare = booking.total_fare
        booking.base_fare_component = Decimal(str(fare_details["base_fare"]))
        booking.distance_fare_component = Decimal(str(fare_details["distance_fare"]))
        booking.time_fare_component = Decimal(str(fare_details["time_fare"]))
        booking.surge_multiplier = Decimal(str(fare_details["surge_multiplier"]))
        booking.night_charge = Decimal(str(fare_details["night_charge"]))
        booking.airport_charge = Decimal(str(fare_details["airport_charge"]))
        booking.discount_amount = Decimal(str(fare_details["discount_amount"]))
        needs_save = True

    if needs_save:
        booking.save()

    return p_lat, p_lng, d_lat, d_lng



# ===============================
# Booking List
# ===============================
@login_required
def booking_list(request):
    if not request.user or not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next=/booking/")

    user_role = getattr(request.user, "role", "CUSTOMER") or "CUSTOMER"

    status_filter = request.GET.get("status", "ALL").upper()
    search = request.GET.get("search", "") or request.GET.get("q", "")
    export = request.GET.get("export")

    bookings = Booking.objects.all()

    if user_role != "ADMIN":
        bookings = bookings.filter(customer=request.user)

    if search:
        from django.db.models import Q
        bookings = bookings.filter(
            Q(pickup_location__icontains=search) |
            Q(drop_location__icontains=search) |
            Q(passenger_name__icontains=search)
        )

    if status_filter != "ALL" and status_filter != "":
        status_map = {
            "PENDING": ["PENDING", "Pending", "SEARCHING_DRIVER"],
            "CONFIRMED": ["ACCEPTED", "Accepted", "CONFIRMED", "TRIP_STARTED", "ACCEPTED_DRIVER"],
            "ACCEPTED": ["ACCEPTED", "Accepted", "CONFIRMED", "TRIP_STARTED", "ACCEPTED_DRIVER"],
            "REJECTED": ["REJECTED", "Rejected", "CANCELLED", "Cancelled"],
            "COMPLETED": ["COMPLETED", "Completed", "TRIP_COMPLETED"],
            "CANCELLED": ["CANCELLED", "Cancelled", "REJECTED", "Rejected"],
        }
        statuses = status_map.get(status_filter, [status_filter])
        bookings = bookings.filter(status__in=statuses)

    # Status counts for stats bar and tab badges
    base_qs = Booking.objects.all() if user_role == "ADMIN" else Booking.objects.filter(customer=request.user)
    pending_c = base_qs.filter(status__in=["PENDING", "Pending", "SEARCHING_DRIVER"]).count()
    confirmed_c = base_qs.filter(status__in=["ACCEPTED", "Accepted", "CONFIRMED", "TRIP_STARTED"]).count()
    completed_c = base_qs.filter(status__in=["COMPLETED", "Completed", "TRIP_COMPLETED"]).count()
    cancelled_c = base_qs.filter(status__in=["REJECTED", "Rejected", "CANCELLED", "Cancelled"]).count()

    if export == "csv" and user_role == "ADMIN":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bookings.csv"'
        writer = csv.writer(response)
        writer.writerow(["ID", "Customer", "Vehicle", "Pickup", "Drop", "Fare", "Status", "Date"])
        for b in bookings:
            writer.writerow([str(b.id), str(b.customer), str(b.vehicle),
                             getattr(b, 'pickup_location', ''), getattr(b, 'drop_location', ''),
                             b.total_fare, b.status, b.created_at])
        return response

    template_name = "booking/booking_list.html" if user_role == "ADMIN" else "booking/customer_booking_list.html"

    return render(request, template_name, {
        "bookings": bookings.order_by("-created_at"),
        "status_filter": status_filter,
        "pending_c": pending_c,
        "confirmed_c": confirmed_c,
        "completed_c": completed_c,
        "cancelled_c": cancelled_c,
    })


@login_required
def accept_booking(request, id):
    if request.user.role not in ["ADMIN", "DRIVER"]:
        messages.error(request, "Only Admins can accept bookings.")
        return redirect("booking_list")
    
    booking = get_object_or_404(Booking, id=id)
    booking.status = "ACCEPTED"
    booking.save()
    messages.success(request, f"✅ Booking #{booking.id} ACCEPTED! Driver Navigation Console launched.")
    return redirect("driver_console", id=booking.id)


@login_required
def driver_console(request, id):
    booking = get_object_or_404(Booking, id=id)

    if booking.status in ["REJECTED", "CANCELLED"]:
        messages.warning(request, f"Booking #{booking.id} has been {booking.status.lower()}. Driver console is unavailable.")
        return redirect("booking_list")

    p_lat, p_lng, d_lat, d_lng = repair_booking_coordinates_and_distance(booking)

    driver_lat = p_lat - 0.012 if p_lat else 12.9600
    driver_lng = p_lng - 0.012 if p_lng else 77.5800

    return render(request, "booking/driver_console.html", {
        "booking": booking,
        "driver_lat": driver_lat,
        "driver_lng": driver_lng,
    })



@login_required
def reject_booking(request, id):
    if request.user.role != "ADMIN":
        messages.error(request, "Only Admins can reject bookings.")
        return redirect("booking_list")
    
    booking = get_object_or_404(Booking, id=id)
    booking.status = "REJECTED"
    booking.save()
    messages.warning(request, f"❌ Booking #{booking.id} has been REJECTED.")
    return redirect("booking_list")


# ===============================
# Add Booking
# ===============================
@login_required
def add_booking(request):
    available_vehicles = Vehicle.objects.filter(is_available=True)
    vehicles_data = {str(v.id): float(v.price_per_km) for v in available_vehicles}
    vehicles_type_data = {v.vehicle_type: float(v.price_per_km) for v in available_vehicles}

    if request.method == "POST":
        post_data = request.POST.copy()

        # Handle Trip Type
        trip_type = post_data.get("trip_type", "ONE_WAY").upper()
        if trip_type not in ["ONE_WAY", "ROUND_TRIP"]:
            trip_type = "ONE_WAY"
        post_data["trip_type"] = trip_type

        # Ensure vehicle_type fallback
        v_id = post_data.get("vehicle_id")
        if not post_data.get("vehicle_type"):
            if v_id:
                try:
                    v = Vehicle.objects.get(id=v_id)
                    post_data["vehicle_type"] = v.vehicle_type
                except Vehicle.DoesNotExist:
                    post_data["vehicle_type"] = "CAR_CAB"
            else:
                post_data["vehicle_type"] = "CAR_CAB"

        if not post_data.get("booking_category"):
            post_data["booking_category"] = "DAILY_RIDE"
        if not post_data.get("payment_method"):
            post_data["payment_method"] = "CASH"

        form = BookingForm(post_data)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.trip_type = trip_type
            booking.outstation_type = trip_type

            # Bind selected Vehicle if passed
            if v_id:
                try:
                    booking.vehicle = Vehicle.objects.get(id=v_id)
                    booking.vehicle_type = booking.vehicle.vehicle_type
                except Vehicle.DoesNotExist:
                    pass

            def safe_float(val, default=0.0):
                try:
                    return float(val) if val else default
                except (ValueError, TypeError):
                    return default

            booking.pickup_location = request.POST.get("pickup_location") or "Pickup Location"
            booking.drop_location = request.POST.get("drop_location") or "Drop Location"
            booking.passenger_name = request.POST.get("passenger_name") or request.user.get_full_name() or request.user.username
            booking.passenger_phone = request.POST.get("passenger_phone") or getattr(request.user, "phone", "") or ""
            booking.driver_notes = request.POST.get("driver_notes", "")

            # If user does not have a phone number on profile, save it
            if booking.passenger_phone and not getattr(request.user, "phone", ""):
                try:
                    request.user.phone = booking.passenger_phone
                    request.user.save(update_fields=["phone"])
                except Exception:
                    pass

            sched_dt = request.POST.get("scheduled_datetime")
            if sched_dt:
                try:
                    from django.utils.dateparse import parse_datetime
                    booking.scheduled_datetime = parse_datetime(sched_dt)
                except Exception:
                    pass

            return_dt = request.POST.get("return_datetime")
            if return_dt:
                try:
                    from django.utils.dateparse import parse_datetime
                    booking.return_datetime = parse_datetime(return_dt)
                except Exception:
                    pass

            # Use 0.0 as default (not Bengaluru) so is_default_bengaluru() triggers re-geocoding
            booking.pickup_lat = safe_float(request.POST.get("pickup_lat"), 0.0)
            booking.pickup_lng = safe_float(request.POST.get("pickup_lng"), 0.0)
            booking.drop_lat   = safe_float(request.POST.get("drop_lat"),   0.0)
            booking.drop_lng   = safe_float(request.POST.get("drop_lng"),   0.0)

            from .pricing import get_real_road_distance, calculate_trip_fare, geocode_address_to_lat_lon

            # If coordinates are missing/zero, geocode from address text immediately
            if not booking.pickup_lat or not booking.pickup_lng or booking.pickup_lat == 0.0:
                g1 = geocode_address_to_lat_lon(booking.pickup_location)
                if g1:
                    booking.pickup_lat, booking.pickup_lng = g1

            if not booking.drop_lat or not booking.drop_lng or booking.drop_lat == 0.0:
                g2 = geocode_address_to_lat_lon(booking.drop_location)
                if g2:
                    booking.drop_lat, booking.drop_lng = g2

            raw_dist = safe_float(request.POST.get("distance"), 0)
            if raw_dist > 0.1:
                booking.distance = Decimal(str(round(raw_dist, 1)))
            else:
                road_dist = get_real_road_distance(
                    booking.pickup_lat, booking.pickup_lng,
                    booking.drop_lat, booking.drop_lng,
                    booking.pickup_location, booking.drop_location
                )
                booking.distance = Decimal(str(road_dist))

            # Get the vehicle's own price_per_km if a vehicle is linked
            vehicle_price_per_km = None
            if booking.vehicle and getattr(booking.vehicle, 'price_per_km', None):
                vehicle_price_per_km = float(booking.vehicle.price_per_km)

            fare_details = calculate_trip_fare(
                vehicle_type=booking.vehicle_type or "CAR_CAB",
                distance_km=float(booking.distance),
                duration_mins=int(float(booking.distance) * 1.5),
                pickup_address=booking.pickup_location,
                drop_address=booking.drop_location,
                booking_category=booking.booking_category,
                outstation_type=booking.trip_type,
                trip_type=booking.trip_type,
                vehicle_price_per_km=vehicle_price_per_km,
            )
            booking.total_fare = Decimal(str(fare_details["total_fare"]))
            booking.fare = booking.total_fare
            booking.status = "PENDING"
            booking.save()
            repair_booking_coordinates_and_distance(booking)

            bno = booking.booking_number or f"#{booking.id}"
            messages.success(request, f"🎉 Booking {bno} submitted! Sent to Admin for review & approval.")
            return redirect(f"/booking/track/{booking.id}/")

        pickup = request.POST.get("pickup_location", "")
        drop = request.POST.get("drop_location", "")
    else:
        pickup = request.GET.get("pickup", "")
        drop = request.GET.get("drop", "")
        date = request.GET.get("date", "")
        time = request.GET.get("time", "")
        vehicle_id = request.GET.get("vehicle", "")

        initial_data = {}
        if date:
            initial_data["booking_date"] = date
        if time:
            initial_data["booking_time"] = time
        if vehicle_id:
            try:
                initial_data["vehicle"] = Vehicle.objects.get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                pass

        form = BookingForm(initial=initial_data)

    return render(
        request,
        "booking/booking_form.html",
        {
            "form": form,
            "pickup": pickup,
            "drop": drop,
            "available_vehicles": available_vehicles,
            "vehicles_data": json.dumps(vehicles_data),
            "vehicles_type_data": json.dumps(vehicles_type_data),
        }
    )


# ===============================
# Booking Details
# ===============================
@login_required
def booking_detail(request, id):
    try:
        booking = Booking.objects.get(id=id)
    except Exception:
        messages.error(request, "Invalid booking ID or booking not found.")
        return redirect("booking_list")

    # Smart role permission check
    is_owner = (str(booking.customer_id) == str(request.user.id))
    b_driver = getattr(booking, 'driver', None)
    is_assigned_driver = (b_driver and (b_driver == request.user or getattr(b_driver, 'user', None) == request.user))
    is_admin_or_partner = (request.user.role in ["ADMIN", "PARTNER"])

    if not (is_owner or is_assigned_driver or is_admin_or_partner):
        messages.error(request, "Access denied. You can only view bookings related to your account.")
        return redirect("booking_list")

    return render(
        request,
        "booking/booking_detail.html",
        {
            "booking": booking
        }
    )


@login_required
def edit_booking(request, id):
    try:
        booking = Booking.objects.get(id=id)
    except Exception:
        messages.error(request, "Invalid booking ID or booking not found.")
        return redirect("booking_list")

    vehicles_data = {str(v.id): float(v.price_per_km) for v in Vehicle.objects.all()}

    if request.user.role == "CUSTOMER" and str(booking.customer_id) != str(request.user.id):
        messages.error(request, "You can only edit your own bookings.")
        return redirect("booking_list")

    if request.method == "POST":

        form = BookingForm(
            request.POST,
            instance=booking
        )

        if form.is_valid():

            booking = form.save(commit=False)

            booking.pickup_location = request.POST.get("pickup_location", booking.pickup_location)
            booking.drop_location = request.POST.get("drop_location", booking.drop_location)

            booking.save()
            repair_booking_coordinates_and_distance(booking)

            messages.success(
                request,
                "Booking Updated Successfully."
            )

            return redirect("booking_list")

    else:

        form = BookingForm(instance=booking)

    return render(
        request,
        "booking/booking_form.html",
        {
            "form": form,
            "pickup": booking.pickup_location,
            "drop": booking.drop_location,
            "vehicles_data": json.dumps(vehicles_data)
        }
    )


# ===============================
# Delete Booking
# ===============================
@login_required
def delete_booking(request, id):
    try:
        booking = Booking.objects.get(id=id)
    except Exception:
        messages.error(request, "Invalid booking ID or booking not found.")
        return redirect("booking_list")

    if request.user.role == "CUSTOMER" and str(booking.customer_id) != str(request.user.id):
        messages.error(request, "You can only delete your own bookings.")
        return redirect("booking_list")

    booking.delete()

    messages.success(
        request,
        "Booking Deleted Successfully."
    )

    return redirect("booking_list")


def seed_default_vehicles_if_empty():
    pass


def search_vehicle(request):
    """Directly opens the Taxi Search / Booking screen with all query parameters."""
    from django.urls import reverse
    params = request.GET.urlencode()
    target_url = reverse("add_booking")
    if params:
        target_url = f"{target_url}?{params}"
    return redirect(target_url)



# ===============================
# Live Ride Tracking
# ===============================
@login_required
def booking_track(request, id):
    try:
        booking = Booking.objects.get(id=id)
    except Exception:
        messages.error(request, "Invalid booking ID or booking not found.")
        return redirect("booking_list")

    # Smart role permission check
    is_owner = (str(booking.customer_id) == str(request.user.id))
    b_driver = getattr(booking, 'driver', None)
    is_assigned_driver = (b_driver and (b_driver == request.user or getattr(b_driver, 'user', None) == request.user))
    is_admin_or_partner = (request.user.role in ["ADMIN", "PARTNER"])

    if not (is_owner or is_assigned_driver or is_admin_or_partner):
        messages.error(request, "Access denied. You can only track bookings related to your account.")
        return redirect("booking_list")

    if not booking.otp:
        import random
        booking.otp = f"{random.randint(100000, 999999)}"
        booking.save()

    repair_booking_coordinates_and_distance(booking)


    steps_keys = [
        ("ACCEPTED",        "Cab Booked",    "✅"),
        ("DRIVER_ASSIGNED", "Driver En Route", "🚖"),
        ("TRIP_STARTED",    "Trip Started",  "🛣️"),
        ("TRIP_COMPLETED",  "Completed",     "🏁"),
    ]

    current_status = getattr(booking, 'status', 'ACCEPTED').upper()
    status_order = [s[0] for s in steps_keys]
    if current_status in ["PENDING", "SEARCHING_DRIVER", "PENDING REVIEW"]:
        current_idx = 0
    elif current_status in ["ACCEPTED", "DRIVER_ASSIGNED", "DRIVER_COMING", "DRIVER_ARRIVED", "CONFIRMED"]:
        current_idx = 1
    elif current_status in ["TRIP_STARTED"]:
        current_idx = 2
    elif current_status in ["TRIP_COMPLETED"]:
        current_idx = 3
    else:
        current_idx = 0

    steps = []
    for idx, (key, label, icon) in enumerate(steps_keys):
        steps.append({
            "key": key,
            "label": label,
            "icon": icon,
            "active": idx == current_idx,
            "completed": idx < current_idx,
        })

    is_rejected_or_cancelled = (current_status in ["REJECTED", "CANCELLED"])

    from django.conf import settings
    return render(request, "booking/live_tracking.html", {
        "booking": booking,
        "steps": steps,
        "current_idx": current_idx,
        "is_stage_pending": (current_idx == 0),
        "is_stage_enroute": (current_idx == 1 and not is_rejected_or_cancelled),
        "is_stage_started": (current_idx == 2),
        "is_stage_completed": (current_idx == 3),
        "is_rejected_or_cancelled": is_rejected_or_cancelled,
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    })


# ===============================
# Sprint 2: Smart Booking APIs
# ===============================
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from realtime.booking_service import find_and_notify_drivers, broadcast_booking_status, log_ride_event
from realtime.cache import booking_lock_cache, ride_request_cache


from .pricing import calculate_trip_fare, Coupon


@require_http_methods(["POST"])
@csrf_exempt
def api_create_booking(request):
    """
    POST /booking/api/create/
    Creates ride request with dynamic pricing breakdown, generates 6-digit OTP, starts smart driver search.
    """
    try:
        data = json.loads(request.body)
        pickup = data.get("pickup_location", "")
        drop   = data.get("drop_location", "")

        from accounts.models import CustomUser
        if request.user.is_authenticated:
            customer_user = request.user
        else:
            customer_user = CustomUser.objects.filter(role="CUSTOMER").first()
            if not customer_user:
                customer_user = CustomUser.objects.create(
                    username="guest_passenger",
                    email="guest@rovexa.com",
                    role="CUSTOMER",
                    first_name="Guest",
                    last_name="Rider"
                )
                customer_user.set_password("Rovexa@123")
                customer_user.save()
        def safe_float(val, default):
            try:
                if val is None or val == "": return default
                return float(val)
            except (ValueError, TypeError):
                return default

        def safe_int(val, default):
            try:
                if val is None or val == "": return default
                return int(val)
            except (ValueError, TypeError):
                return default

        p_lat      = safe_float(data.get("pickup_lat"), 0)
        p_lng      = safe_float(data.get("pickup_lng"), 0)
        d_lat      = safe_float(data.get("drop_lat"), 0)
        d_lng      = safe_float(data.get("drop_lng"), 0)
        v_type     = data.get("vehicle_type") or "MINI"
        dist_val   = safe_float(data.get("distance"), 0)
        dur_val    = safe_int(data.get("estimated_duration"), 0)
        b_category = data.get("booking_category") or "DAILY_RIDE"
        sched_dt   = data.get("scheduled_datetime")
        rental_pkg = data.get("rental_package", "")
        out_type   = data.get("outstation_type") or "ONE_WAY"
        coupon_code = data.get("coupon_code", "")

        from .pricing import get_real_road_distance, calculate_trip_fare
        if dist_val < 0.1:
            dist_val = get_real_road_distance(p_lat, p_lng, d_lat, d_lng, pickup, drop)
        if dur_val <= 0:
            dur_val = max(1, int(dist_val * 2))

        # Compute dynamic pricing breakdown
        fare_details = calculate_trip_fare(
            vehicle_type=v_type,
            distance_km=dist_val,
            duration_mins=dur_val,
            pickup_address=pickup,
            drop_address=drop,
            coupon_code=coupon_code,
            booking_category=b_category,
            rental_package=rental_pkg,
            outstation_type=out_type,
        )

        total_fare_dec = Decimal(str(fare_details["total_fare"]))

        booking = Booking.objects.create(
            customer=customer_user,
            pickup_location=pickup,
            drop_location=drop,
            pickup_lat=p_lat,
            pickup_lng=p_lng,
            drop_lat=d_lat,
            drop_lng=d_lng,
            vehicle_type=v_type,
            distance=Decimal(str(dist_val)),
            total_fare=total_fare_dec,
            fare=total_fare_dec,
            base_fare_component=Decimal(str(fare_details["base_fare"])),
            distance_fare_component=Decimal(str(fare_details["distance_fare"])),
            time_fare_component=Decimal(str(fare_details["time_fare"])),
            surge_multiplier=Decimal(str(fare_details["surge_multiplier"])),
            night_charge=Decimal(str(fare_details["night_charge"])),
            airport_charge=Decimal(str(fare_details["airport_charge"])),
            discount_amount=Decimal(str(fare_details["discount_amount"])),
            coupon_code=fare_details["coupon_code"],
            estimated_duration=dur_val,
            passenger_name=data.get("passenger_name") or customer_user.get_full_name() or customer_user.username,
            passenger_phone=data.get("passenger_phone") or getattr(customer_user, "phone", "") or "",
            driver_notes=data.get("driver_notes", ""),
            booking_category=b_category,
            rental_package=rental_pkg,
            outstation_type=out_type,
            status="PENDING",
            payment_method=data.get("payment_method", "CASH"),
        )

        log_ride_event(str(booking.id), "BOOKING_CREATED", actor_id=str(customer_user.id), actor_role="CUSTOMER")
        repair_booking_coordinates_and_distance(booking)

        return JsonResponse({

            "success": True,
            "booking_id": str(booking.id),
            "otp": booking.otp,
            "status": booking.status,
            "fare_breakdown": fare_details,
            "redirect_url": f"/booking/track/{booking.id}/",
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_verify_otp(request):
    """
    POST /booking/api/verify-otp/
    Driver inputs OTP to start trip.
    """
    try:
        data       = json.loads(request.body)
        booking_id = data.get("booking_id")
        input_otp  = str(data.get("otp", "")).strip()

        booking = Booking.objects.get(id=booking_id)

        if booking.otp == input_otp:
            booking.otp_verified = True
            booking.status       = "TRIP_STARTED"
            booking.save()

            log_ride_event(str(booking.id), "OTP_VERIFIED", actor_id=str(request.user.id), actor_role="DRIVER")
            log_ride_event(str(booking.id), "TRIP_STARTED", actor_id=str(request.user.id), actor_role="DRIVER")

            broadcast_booking_status(str(booking.id), "TRIP_STARTED", {
                "message": "OTP Verified! Trip has started.",
            })

            return JsonResponse({
                "success": True,
                "message": "OTP Verified successfully! Trip started.",
                "status": "TRIP_STARTED",
            })
        else:
            return JsonResponse({
                "success": False,
                "message": "Incorrect OTP. Please check with customer.",
            }, status=400)

    except Booking.DoesNotExist:
        return JsonResponse({"success": False, "message": "Booking not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_complete_trip(request):
    """
    POST /booking/api/complete-trip/
    Driver marks trip as completed.
    """
    try:
        data       = json.loads(request.body)
        booking_id = data.get("booking_id")

        booking = Booking.objects.get(id=booking_id)
        booking.status         = "TRIP_COMPLETED"
        booking.payment_status = "PAID"
        booking.save()

        log_ride_event(str(booking.id), "TRIP_COMPLETED", actor_id=str(request.user.id), actor_role="DRIVER")

        broadcast_booking_status(str(booking.id), "TRIP_COMPLETED", {
            "fare": float(booking.total_fare),
            "payment_status": booking.payment_status,
        })

        return JsonResponse({
            "success": True,
            "message": "Trip completed successfully!",
            "status": "TRIP_COMPLETED",
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_driver_respond(request):
    """
    POST /booking/api/driver-respond/
    Driver accepts or rejects ride offer.
    Uses distributed Redis locking to prevent duplicate acceptances.
    """
    try:
        data       = json.loads(request.body)
        booking_id = data.get("booking_id")
        action     = data.get("action")  # "ACCEPT" or "REJECT"
        driver_id  = str(request.user.id)

        if action == "ACCEPT":
            # Acquire Redis lock atomically
            acquired = booking_lock_cache.acquire_lock(booking_id, driver_id)
            if not acquired:
                return JsonResponse({
                    "success": False,
                    "message": "Another driver accepted this ride first.",
                }, status=409)

            booking = Booking.objects.get(id=booking_id)
            try:
                from driver.models import Driver
                d = Driver.objects.get(user=request.user)
                booking.driver = d
            except Exception:
                pass

            booking.status = "DRIVER_ASSIGNED"
            booking.save()

            log_ride_event(booking_id, "DRIVER_ASSIGNED", actor_id=driver_id, actor_role="DRIVER")

            broadcast_booking_status(booking_id, "DRIVER_ASSIGNED", {
                "driver_id": driver_id,
                "driver_name": request.user.get_full_name() or request.user.username,
                "phone": getattr(request.user, "phone", ""),
                "otp": booking.otp,
            })

            return JsonResponse({
                "success": True,
                "message": "Ride accepted successfully!",
                "otp": booking.otp,
                "status": "DRIVER_ASSIGNED",
            })

        elif action == "REJECT":
            ride_request_cache.set_driver_response(booking_id, driver_id, "REJECTED")
            log_ride_event(booking_id, "DRIVER_REJECTED", actor_id=driver_id, actor_role="DRIVER")
            return JsonResponse({"success": True, "message": "Ride rejected."})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def cancel_booking(request, id):
    """Cancel booking view."""
    try:
        booking = Booking.objects.get(id=id)
        booking.status = "CANCELLED"
        booking.save()

        booking_lock_cache.release_lock(str(id))
        broadcast_booking_status(str(id), "BOOKING_CANCELLED", {"reason": "Cancelled by customer"})
        log_ride_event(str(id), "BOOKING_CANCELLED", actor_id=str(request.user.id), actor_role="CUSTOMER")

        messages.success(request, "Booking cancelled.")
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["POST"])
@csrf_exempt
def api_calculate_fare(request):
    """
    POST /booking/api/calculate-fare/
    Body: {"vehicle_type": "CAR_CAB", "distance": 10.5, "duration": 25, "pickup": "...", "drop": "...", "trip_type": "ONE_WAY"|"ROUND_TRIP"}
    Returns detailed dynamic fare breakdown including One Way and Round Trip pricing.
    """
    try:
        data   = json.loads(request.body)
        v_type = data.get("vehicle_type", "CAR_CAB")
        dist   = float(data.get("distance") or 0)
        dur    = int(data.get("duration") or 0)
        pickup = data.get("pickup", "")
        drop   = data.get("drop", "")
        p_lat  = float(data.get("pickup_lat") or 0)
        p_lng  = float(data.get("pickup_lng") or 0)
        d_lat  = float(data.get("drop_lat") or 0)
        d_lng  = float(data.get("drop_lng") or 0)
        coupon     = data.get("coupon", "")
        b_category = data.get("booking_category", "DAILY_RIDE")
        rental_pkg = data.get("rental_package", "")
        trip_type  = data.get("trip_type", "ONE_WAY")
        out_type   = data.get("outstation_type", trip_type)
        # Vehicle's admin-set per-km rate (sent from frontend data-price attribute)
        vehicle_price_per_km = float(data.get("rate", 0) or data.get("vehicle_price_per_km", 0) or 0)

        if dist < 0.1:
            from .pricing import get_real_road_distance
            dist = get_real_road_distance(p_lat, p_lng, d_lat, d_lng, pickup, drop)
        if dur <= 0:
            dur = max(1, int(dist * 2))

        breakdown = calculate_trip_fare(
            vehicle_type=v_type,
            distance_km=dist,
            duration_mins=dur,
            pickup_address=pickup,
            drop_address=drop,
            coupon_code=coupon,
            booking_category=b_category,
            rental_package=rental_pkg,
            outstation_type=out_type,
            trip_type=trip_type,
            vehicle_price_per_km=vehicle_price_per_km if vehicle_price_per_km > 0 else None,
        )

        return JsonResponse({"success": True, "fare_details": breakdown})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_apply_coupon(request):
    """
    POST /booking/api/apply-coupon/
    Body: {"coupon_code": "ROVEXA10", "trip_fare": 200}
    Validates coupon and calculates discount amount.
    """
    try:
        data = json.loads(request.body)
        code = data.get("coupon_code", "").strip()
        fare = Decimal(str(data.get("trip_fare", 0)))

        cp = Coupon.objects.get(code__iexact=code, is_active=True)
        now = timezone.now()

        if cp.valid_until and cp.valid_until < now:
            return JsonResponse({"success": False, "message": "Coupon code has expired."}, status=400)
        if cp.uses_count >= cp.max_uses:
            return JsonResponse({"success": False, "message": "Coupon usage limit reached."}, status=400)
        if fare < cp.min_trip_fare:
            return JsonResponse({"success": False, "message": f"Minimum trip fare of ₹{cp.min_trip_fare} required."}, status=400)

        discount = min((fare * cp.discount_percent) / Decimal("100"), cp.max_discount_amount)
        new_total = max(Decimal("30.00"), fare - discount)

        return JsonResponse({
            "success": True,
            "code": cp.code,
            "discount_percent": float(cp.discount_percent),
            "discount_amount": round(float(discount), 2),
            "new_total": round(float(new_total), 2),
            "message": f"Coupon {cp.code} applied! Saved ₹{round(float(discount), 2)}",
        })

    except Coupon.DoesNotExist:
        return JsonResponse({"success": False, "message": "Invalid promo code."}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_rate_driver(request):
    """
    POST /booking/api/rate-driver/
    Body: {"booking_id": "...", "rating": 5, "comment": "Great trip!"}
    Updates Booking rating and recalculates Driver aggregate rating_score.
    """
    try:
        from django.db.models import Avg
        data       = json.loads(request.body)
        booking_id = data.get("booking_id")
        rating_val = int(data.get("rating", 5))
        comment    = data.get("comment", "").strip()

        if rating_val < 1 or rating_val > 5:
            return JsonResponse({"success": False, "message": "Rating must be between 1 and 5."}, status=400)

        booking = Booking.objects.get(id=booking_id)

        # Check customer ownership
        if str(booking.customer_id) != str(request.user.id):
            return JsonResponse({"success": False, "message": "Access denied."}, status=403)

        booking.rating = rating_val
        booking.review_comment = comment
        booking.rating_date = timezone.now()
        booking.save()

        # Recalculate driver aggregate score
        if booking.driver:
            driver = booking.driver
            completed_ratings = Booking.objects.filter(driver=driver, rating__isnull=False)
            avg_res = completed_ratings.aggregate(Avg("rating"))["rating__avg"]
            if avg_res:
                driver.rating_score = round(Decimal(str(avg_res)), 2)
                driver.total_ratings_count = completed_ratings.count()
                driver.save()

        return JsonResponse({
            "success": True,
            "message": "Thank you for rating your ride!",
            "rating": rating_val,
            "new_driver_score": float(booking.driver.rating_score) if booking.driver else 5.0
        })

    except Booking.DoesNotExist:
        return JsonResponse({"success": False, "message": "Booking not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_trigger_sos(request):
    """
    POST /booking/api/sos/
    Body: {"booking_id": "...", "lat": 12.97, "lng": 77.59, "address": "..."}
    Triggers an emergency SOS alert, logs event, and broadcasts to admin_operations.
    """
    try:
        from .models import EmergencyAlert
        data       = json.loads(request.body)
        booking_id = data.get("booking_id")
        lat_val    = float(data.get("lat", 0))
        lng_val    = float(data.get("lng", 0))
        addr       = data.get("address", "").strip()

        booking = Booking.objects.get(id=booking_id)

        alert = EmergencyAlert.objects.create(
            booking=booking,
            user=request.user,
            lat=lat_val or booking.pickup_lat,
            lng=lng_val or booking.pickup_lng,
            current_address=addr or booking.pickup_location,
            status="ACTIVE"
        )

        log_ride_event(str(booking.id), "EMERGENCY_SOS_TRIGGERED", actor_id=str(request.user.id), actor_role=request.user.role)

        # Broadcast high-priority WebSocket alert to admin operations room
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            cl = get_channel_layer()
            if cl:
                async_to_sync(cl.group_send)(
                    "admin_operations",
                    {
                        "type": "sos.alert",
                        "alert_id": str(alert.id),
                        "booking_id": str(booking.id),
                        "user_name": request.user.get_full_name() or request.user.username,
                        "user_phone": getattr(request.user, "phone", ""),
                        "driver_name": booking.driver.full_name if booking.driver else "Unassigned",
                        "vehicle_type": booking.vehicle_type,
                        "lat": alert.lat,
                        "lng": alert.lng,
                        "address": alert.current_address,
                        "time": timezone.now().strftime("%I:%M %p"),
                    }
                )
        except Exception:
            pass

        return JsonResponse({
            "success": True,
            "alert_id": str(alert.id),
            "message": "🚨 Emergency SOS alert triggered! Admin operations team and emergency response have been notified."
        })

    except Booking.DoesNotExist:
        return JsonResponse({"success": False, "message": "Booking not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def public_track_ride(request, share_token):
    """
    Public shareable live ride tracking page (No login required).
    """
    try:
        booking = Booking.objects.get(share_token=share_token)
    except Booking.DoesNotExist:
        messages.error(request, "Public tracking link invalid or expired.")
        return render(request, "booking/public_track.html", {"error": "Invalid tracking link"})

    from django.conf import settings
    return render(request, "booking/public_track.html", {
        "booking": booking,
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", ""),
    })


# ===============================
# Sprint 9: Advanced Booking Views
# ===============================
from django.http import HttpResponse
from .models import FareSplit

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_split_fare(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get("booking_id")
        email = data.get("participant_email", "").strip()
        amount = Decimal(str(data.get("split_amount", "0")))

        booking = get_object_or_404(Booking, id=booking_id)
        if str(booking.customer_id) != str(request.user.id):
            return JsonResponse({"success": False, "message": "Only the ride creator can request fare splits."}, status=403)

        split = FareSplit.objects.create(
            booking=booking,
            requester=request.user,
            participant_email=email,
            split_amount=amount,
            status="PENDING"
        )

        return JsonResponse({"success": True, "message": f"Fare split request sent to {email}."})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
def download_calendar_ics(request, id):
    try:
        booking = get_object_or_404(Booking, id=id)
        start_time = booking.scheduled_datetime or booking.created_at
        end_time = start_time + timedelta(minutes=booking.estimated_duration or 30)

        dt_start = start_time.strftime("%Y%m%dT%H%M%SZ")
        dt_end = end_time.strftime("%Y%m%dT%H%M%SZ")

        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Rovexa Cabs//Ride Schedule//EN
BEGIN:VEVENT
SUMMARY:🚖 Rovexa Ride #{booking.id} ({booking.booking_category})
DESCRIPTION:Rovexa Cab Ride from {booking.pickup_location} to {booking.drop_location}. Vehicle: {booking.vehicle_type}. Est. Fare: ₹{booking.total_fare}
LOCATION:{booking.pickup_location}
DTSTART:{dt_start}
DTEND:{dt_end}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""

        response = HttpResponse(ics_content.strip(), content_type="text/calendar")
        response["Content-Disposition"] = f'attachment; filename="rovexa_ride_{booking.id}.ics"'
        return response
    except Exception as e:
        messages.error(request, "Unable to generate calendar invite.")
        return redirect("booking_list")


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_toggle_favorite_driver(request):
    return JsonResponse({"success": True, "is_favorite": False, "message": "Feature deprecated."})


def api_nearby_drivers(request):
    return JsonResponse({"success": True, "drivers": []})


@csrf_exempt
@require_http_methods(["POST"])
def api_send_chat(request):
    try:
        data = json.loads(request.body)
        booking_id = data.get("booking_id")
        msg_text = data.get("message", "").strip()
        sender_type = data.get("sender", "CUSTOMER")
        sender_name = request.user.username if request.user.is_authenticated else sender_type

        if not booking_id or not msg_text:
            return JsonResponse({"success": False, "error": "Missing booking_id or message"}, status=400)

        from .models import Booking, RideChatMessage
        booking = Booking.objects.get(id=booking_id)
        msg_obj = RideChatMessage.objects.create(
            booking=booking,
            sender=sender_type,
            sender_name=sender_name,
            message=msg_text
        )

        return JsonResponse({
            "success": True,
            "message_id": str(msg_obj.id),
            "sender": msg_obj.sender,
            "sender_name": msg_obj.sender_name,
            "message": msg_obj.message,
            "timestamp": msg_obj.created_at.strftime("%H:%M")
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def api_get_chat_messages(request, booking_id):
    try:
        from .models import RideChatMessage
        msgs = RideChatMessage.objects.filter(booking_id=booking_id).order_by("created_at")
        results = []
        for m in msgs:
            results.append({
                "id": str(m.id),
                "sender": m.sender,
                "sender_name": m.sender_name,
                "message": m.message,
                "time": m.created_at.strftime("%H:%M")
            })
        return JsonResponse({"success": True, "messages": results})
    except Exception as e:
        return JsonResponse({"success": False, "messages": [], "error": str(e)})


def api_booking_status(request, booking_id):
    try:
        from .models import Booking
        booking = Booking.objects.get(id=booking_id)

        p_lat, p_lng, d_lat, d_lng = repair_booking_coordinates_and_distance(booking)


        status_upper = str(booking.status or "ACCEPTED").upper()

        if status_upper == "TRIP_COMPLETED":
            driver_lat = d_lat
            driver_lng = d_lng
        elif status_upper == "TRIP_STARTED":
            driver_lat = (p_lat + d_lat) / 2.0
            driver_lng = (p_lng + d_lng) / 2.0
        else:
            # Pre-trip / Pending / Accepted / Driver Assigned: cab is en route to pickup
            driver_lat = p_lat - 0.005
            driver_lng = p_lng - 0.005

        driver_info = {}
        if booking.driver or booking.vehicle:
            d_name = ""
            d_phone = ""
            d_rating = 4.9
            v_name = "Rovexa Cab"
            v_num = ""

            if booking.vehicle:
                v_name = booking.vehicle.vehicle_name
                v_num = booking.vehicle.vehicle_number
                d_name = booking.vehicle.driver_name
                d_phone = booking.vehicle.driver_phone
                d_rating = float(booking.vehicle.driver_rating or 4.9)

            if booking.driver:
                d_name = d_name or booking.driver.get_full_name() or booking.driver.username
                d_phone = d_phone or getattr(booking.driver, "phone", "") or "+91 98452 98351"

            driver_info = {
                "name": d_name or "Ramesh Kumar",
                "phone": d_phone or "+91 98452 98351",
                "rating": d_rating,
                "vehicle": v_name,
                "vehicle_number": v_num,
                "lat": driver_lat,
                "lng": driver_lng,
            }

        return JsonResponse({
            "success": True,
            "status": booking.status,
            "otp": booking.otp,
            "otp_verified": getattr(booking, "otp_verified", False),
            "fare": float(booking.total_fare or 0),
            "distance": float(booking.distance or 0),
            "driver": driver_info
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=200)





