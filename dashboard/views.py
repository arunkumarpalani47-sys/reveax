import csv
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from accounts.decorators import role_required
from accounts.models import CustomUser
from vehicle.models import Vehicle
from booking.models import Booking
from payment.models import Payment


@login_required
def admin_dashboard(request):
    if getattr(request.user, "role", "") == "CUSTOMER":
        return redirect("customer_dashboard")
    elif getattr(request.user, "role", "") in ["DRIVER", "PARTNER"]:
        return redirect("booking_list")
    customer_count      = CustomUser.objects.filter(role="CUSTOMER").count()
    vehicle_count       = Vehicle.objects.count()
    booking_count       = Booking.objects.count()
    payment_count       = Payment.objects.count()
    available_vehicle   = Vehicle.objects.filter(is_available=True).count()

    # Fleet Category breakdown
    sedan_count = Vehicle.objects.filter(vehicle_type="SEDAN").count()
    suv_count   = Vehicle.objects.filter(vehicle_type="SUV").count()
    hatch_count = Vehicle.objects.filter(vehicle_type__in=["MINI", "HATCHBACK"]).count()

    # Booking status counts
    pending_bookings = list(Booking.objects.filter(status__in=["PENDING", "Pending", "SEARCHING_DRIVER"]).order_by("-created_at")[:5])
    pending_count    = Booking.objects.filter(status__in=["PENDING", "Pending", "SEARCHING_DRIVER"]).count()
    confirmed_count  = Booking.objects.filter(status__in=["ACCEPTED", "Accepted", "CONFIRMED", "TRIP_STARTED", "ACCEPTED_DRIVER"]).count()
    completed_count  = Booking.objects.filter(status__in=["COMPLETED", "Completed", "TRIP_COMPLETED"]).count()
    cancelled_count  = Booking.objects.filter(status__in=["REJECTED", "Rejected", "CANCELLED", "Cancelled"]).count()

    # Recent bookings
    recent_bookings = list(Booking.objects.all().order_by("-created_at")[:10])

    # Total revenue
    all_payments = Payment.objects.all()
    total_revenue = sum(float(p.amount or 0) for p in all_payments)
    if total_revenue == 0 and booking_count > 0:
        total_revenue = sum(float(b.total_fare or b.fare or 0) for b in Booking.objects.filter(status__in=["ACCEPTED", "Accepted", "COMPLETED", "Completed"]))

    context = {
        "customer_count":    customer_count,
        "vehicle_count":     vehicle_count,
        "booking_count":     booking_count,
        "payment_count":     payment_count,
        "available_vehicle": available_vehicle,
        "sedan_count":       sedan_count,
        "suv_count":         suv_count,
        "hatch_count":       hatch_count,
        "pending_bookings":  pending_bookings,
        "pending_count":     pending_count,
        "confirmed_count":   confirmed_count,
        "completed_count":   completed_count,
        "cancelled_count":   cancelled_count,
        "recent_bookings":   recent_bookings,
        "total_revenue":     total_revenue,
    }
    return render(request, "admin/dashboard.html", context)


@role_required("ADMIN")
def admin_reports(request):
    export = request.GET.get("export")

    if export == "bookings":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="bookings.csv"'
        writer = csv.writer(response)
        writer.writerow(["ID", "Customer", "Vehicle", "Pickup", "Dropoff", "Fare", "Status", "Date"])
        for b in Booking.objects.all():
            writer.writerow([
                str(b.id), str(b.customer), str(b.vehicle),
                getattr(b, 'pickup_location', ''), getattr(b, 'drop_location', ''),
                b.total_fare, b.status, b.created_at,
            ])
        return response

    if export == "payments":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payments.csv"'
        writer = csv.writer(response)
        writer.writerow(["ID", "Booking", "Amount", "Status", "Date"])
        for p in Payment.objects.all():
            writer.writerow([str(p.id), str(p.booking), p.amount, p.status, p.created_at])
        return response

    if export == "users":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="users.csv"'
        writer = csv.writer(response)
        writer.writerow(["Name", "Email", "Role", "Joined"])
        for u in CustomUser.objects.all():
            writer.writerow([u.display_name, u.email, u.role, u.date_joined])
        return response

    total_revenue   = sum(float(p.amount or 0) for p in Payment.objects.all())
    booking_count   = Booking.objects.count()
    customer_count  = CustomUser.objects.filter(role="CUSTOMER").count()
    pending_count   = Booking.objects.filter(status__in=["PENDING", "Pending"]).count()
    confirmed_count = Booking.objects.filter(status__in=["ACCEPTED", "Accepted", "CONFIRMED"]).count()
    completed_count = Booking.objects.filter(status__in=["COMPLETED", "Completed"]).count()
    cancelled_count = Booking.objects.filter(status__in=["REJECTED", "Rejected", "CANCELLED", "Cancelled"]).count()

    context = {
        "total_revenue":   total_revenue,
        "booking_count":   booking_count,
        "customer_count":  customer_count,
        "pending_count":   pending_count,
        "confirmed_count": confirmed_count,
        "completed_count": completed_count,
        "cancelled_count": cancelled_count,
    }
    return render(request, "admin/reports.html", context)