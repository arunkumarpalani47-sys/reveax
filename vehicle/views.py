from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages

from accounts.decorators import role_required
from .models import Vehicle
from .forms import VehicleForm


def _vehicles_queryset(request):
    return Vehicle.objects.all()


def _build_form(request, *args, **kwargs):
    return VehicleForm(*args, **kwargs)


@role_required("ADMIN")
def vehicle_list(request):

    search = request.GET.get("search") or ""

    vehicles = _vehicles_queryset(request)

    if search:
        vehicles = vehicles.filter(
            Q(vehicle_name__icontains=search) |
            Q(vehicle_number__icontains=search) |
            Q(brand__icontains=search) |
            Q(model__icontains=search)
        )

    paginator = Paginator(vehicles, 10)
    page = request.GET.get("page")
    vehicles = paginator.get_page(page)

    context = {
        "vehicles": vehicles,
        "search": search,
    }

    return render(request, "vehicle/vehicle_list.html", context)


@role_required("ADMIN")
def add_vehicle(request):

    if request.method == "POST":

        form = _build_form(request, request.POST, request.FILES)

        if form.is_valid():
            vehicle = form.save(commit=False)
            vehicle.owner = request.user
            vehicle.save()
            messages.success(request, "Vehicle added successfully.")
            return redirect("vehicle_list")

    else:
        form = _build_form(request)

    return render(request, "vehicle/vehicle_form.html", {"form": form})


@role_required("ADMIN")
def edit_vehicle(request, id):

    vehicle = get_object_or_404(_vehicles_queryset(request), id=id)

    if request.method == "POST":

        form = _build_form(request, request.POST, request.FILES, instance=vehicle)

        if form.is_valid():
            form.save()
            messages.success(request, "Vehicle updated successfully.")
            return redirect("vehicle_list")

    else:
        form = _build_form(request, instance=vehicle)

    return render(request, "vehicle/vehicle_form.html", {"form": form})


@role_required("ADMIN")
def delete_vehicle(request, id):
    vehicle = get_object_or_404(_vehicles_queryset(request), id=id)
    vname = vehicle.vehicle_name
    vehicle.delete()
    messages.success(request, f"🗑️ Vehicle '{vname}' has been permanently deleted.")
    return redirect("vehicle_list")


@role_required("ADMIN")
def toggle_vehicle(request, id):
    from django.http import JsonResponse
    vehicle = get_object_or_404(_vehicles_queryset(request), id=id)
    vehicle.is_available = not vehicle.is_available
    vehicle.save()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "success", "is_available": vehicle.is_available})
    messages.success(request, f"Vehicle '{vehicle.vehicle_name}' status updated to {'Available' if vehicle.is_available else 'Unavailable'}.")
    return redirect("vehicle_list")
