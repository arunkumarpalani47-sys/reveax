from django.contrib import admin
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):

    list_display = (
        "vehicle_name",
        "brand",
        "vehicle_number",
        "owner",
        "vehicle_type",
        "price_per_km",
        "is_available",
    )

    search_fields = (
        "vehicle_name",
        "vehicle_number",
        "brand",
    )

    list_filter = (
        "vehicle_type",
        "fuel_type",
        "is_available",
    )