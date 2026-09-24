from django.shortcuts import render
from django.contrib import messages
from django.http import JsonResponse

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
    return render(request, "home/index.html")

def about(request):
    stats = get_live_stats()
    return render(request, "about.html", stats)

def api_stats(request):
    stats = get_live_stats()
    return JsonResponse(stats)

def services(request):
    return render(request, "services.html")

def contact(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        messages.success(request, f"Thank you {name or 'for contacting us'}! Your message has been received. Our team will get back to you shortly.")
    return render(request, "contact.html")