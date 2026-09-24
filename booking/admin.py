from django.contrib import admin
from .models import Booking, PricingRule, Coupon


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "customer",
        "vehicle",
        "vehicle_type",
        "status",
        "total_fare",
        "surge_multiplier",
        "coupon_code",
        "created_at",
    )

    list_filter = (
        "status",
        "vehicle_type",
        "created_at",
    )

    search_fields = (
        "customer__username",
        "pickup_location",
        "drop_location",
        "otp",
    )


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "vehicle_type",
        "display_name",
        "base_fare",
        "rate_per_km",
        "rate_per_min",
        "surge_multiplier",
        "night_charge_percent",
        "airport_flat_charge",
        "is_active",
    )
    list_editable = ("base_fare", "rate_per_km", "rate_per_min", "surge_multiplier", "is_active")
    search_fields = ("vehicle_type", "display_name")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_percent",
        "max_discount_amount",
        "min_trip_fare",
        "uses_count",
        "max_uses",
        "is_active",
        "valid_until",
    )
    list_editable = ("discount_percent", "max_discount_amount", "is_active")
    search_fields = ("code",)