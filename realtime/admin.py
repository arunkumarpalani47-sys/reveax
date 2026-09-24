from django.contrib import admin
from .models import DriverLocation, RideLog


@admin.register(DriverLocation)
class DriverLocationAdmin(admin.ModelAdmin):
    list_display  = ["driver_id", "lat", "lng", "speed", "is_online", "last_seen"]
    list_filter   = ["is_online"]
    search_fields = ["driver_id"]
    ordering      = ["-last_seen"]


@admin.register(RideLog)
class RideLogAdmin(admin.ModelAdmin):
    list_display  = ["booking_id", "event_type", "actor_role", "actor_id", "created_at"]
    list_filter   = ["event_type", "actor_role"]
    search_fields = ["booking_id", "actor_id"]
    ordering      = ["-created_at"]
    readonly_fields = ["booking_id", "event_type", "actor_id", "actor_role",
                       "lat", "lng", "metadata", "created_at"]
