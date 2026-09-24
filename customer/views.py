from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from booking.models import Booking
from vehicle.models import Vehicle

@login_required
def customer_dashboard(request):
    if getattr(request.user, "role", "") == "ADMIN":
        return redirect("admin_dashboard")
    elif getattr(request.user, "role", "") in ["DRIVER", "PARTNER"]:
        return redirect("booking_list")

    user_bookings = Booking.objects.filter(customer=request.user).order_by("-created_at")

    total_bookings = user_bookings.count()
    pending_c   = user_bookings.filter(status__in=["PENDING", "Pending", "SEARCHING_DRIVER"]).count()
    accepted_c  = user_bookings.filter(status__in=["ACCEPTED", "Accepted", "CONFIRMED", "TRIP_STARTED", "ACCEPTED_DRIVER"]).count()
    completed_c = user_bookings.filter(status__in=["COMPLETED", "Completed", "TRIP_COMPLETED"]).count()
    rejected_c  = user_bookings.filter(status__in=["REJECTED", "Rejected", "CANCELLED", "Cancelled"]).count()

    recent_bookings = list(user_bookings[:6])
    available_vehicles = Vehicle.objects.filter(is_available=True)[:6]

    context = {
        "total_bookings":     total_bookings,
        "pending_count":      pending_c,
        "accepted_count":     accepted_c,
        "completed_count":    completed_c,
        "rejected_count":     rejected_c,
        "recent_bookings":    recent_bookings,
        "available_vehicles": available_vehicles,
    }

    return render(request, "customer/dashboard.html", context)