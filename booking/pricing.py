"""
Dynamic Pricing Engine for Rovexa.

Calculates fare based on:
  - Base Fare
  - Distance Rate (per km)
  - Time Rate (per minute)
  - Dynamic Surge Multiplier (Peak hours 8-10am / 5-8pm, High demand zones)
  - Night Surcharge (10 PM to 5 AM: +20%)
  - Airport Surcharge (Flat ₹50 for airport trips)
  - Promo / Coupon Discount Engine
"""

from decimal import Decimal
import math
import urllib.request
import json
from django.utils import timezone
from .models import PricingRule, Coupon

import urllib.parse

def geocode_address_to_lat_lon(address: str):
    """Geocodes a text address to (lat, lon) tuple using Nominatim API with query fallback."""
    if not address or len(address.strip()) < 3:
        return None

    def _try_geocode(q_str):
        try:
            encoded = urllib.parse.quote(q_str.strip())
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded}&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'RovexaTaxiApp/1.0 (contact@rovexa.com)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if data and len(data) > 0:
                    return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception:
            pass
        return None

    # 1. Try full address string
    res = _try_geocode(address)
    if res:
        return res

    # 2. Fallback: try primary city/region name
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) > 1:
        res_simp = _try_geocode(f"{parts[0]}, India")
        if res_simp:
            return res_simp

    return None

def get_real_road_distance(lat1, lon1, lat2, lon2, pickup_address="", drop_address="") -> float:
    """
    Fetches exact road driving distance in kilometers from OSRM Routing Engine.
    Falls back to Nominatim Geocoding or precise Haversine * 1.35 if needed.
    """
    try:
        lat1, lon1 = float(lat1 or 0), float(lon1 or 0)
        lat2, lon2 = float(lat2 or 0), float(lon2 or 0)
        # Fix swapped coordinates (India lat ~8-37, lon ~68-97)
        if lat1 > 50 and lon1 < 40:
            lat1, lon1 = lon1, lat1
        if lat2 > 50 and lon2 < 40:
            lat2, lon2 = lon2, lat2
    except (ValueError, TypeError):
        lat1, lon1, lat2, lon2 = 0, 0, 0, 0

    # Check if coordinates are missing, identical, or form default placeholders (12.9716/12.9352)
    is_default_coords = (
        (abs(lat1 - 12.9716) < 0.005 and abs(lon1 - 77.5946) < 0.005 and abs(lat2 - 12.9352) < 0.005 and abs(lon2 - 77.6245) < 0.005) or
        (not lat1 or not lat2 or (abs(lat1 - lat2) < 0.0001 and abs(lon1 - lon2) < 0.0001))
    )

    if is_default_coords and pickup_address and drop_address:
        g1 = geocode_address_to_lat_lon(pickup_address)
        g2 = geocode_address_to_lat_lon(drop_address)
        if g1 and g2:
            lat1, lon1 = g1
            lat2, lon2 = g2

    # If pickup and drop locations are identical or missing
    if abs(lat1 - lat2) < 0.0001 and abs(lon1 - lon2) < 0.0001:
        if pickup_address and drop_address and pickup_address.strip().lower() == drop_address.strip().lower():
            return 0.0

    if not (lat1 and lon1 and lat2 and lon2):
        return 5.0

    # 1. Try OSRM Routing Engine for exact driving road distance
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        req = urllib.request.Request(url, headers={'User-Agent': 'RovexaTaxiApp/1.0'})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if data.get("routes") and len(data["routes"]) > 0:
                dist_meters = data["routes"][0]["distance"]
                dist_km = round(dist_meters / 1000.0, 1)
                if dist_km > 0.0:
                    return dist_km
    except Exception:
        pass

    # 2. Precise Haversine Formula with 1.35x Road Factor
    try:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        a = min(1.0, max(0.0, a))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        straight_km = R * c
        if straight_km < 0.1:
            return 0.0
        return max(0.5, round(straight_km * 1.35, 1))
    except Exception:
        return 5.0

DEFAULT_RULES = {
    "CAR_CAB":   {"display_name": "Rovexa Car Cab",   "base_fare": 40, "rate_per_km": 15, "rate_per_min": 2.0, "night_pct": 20, "airport": 50, "surge": 1.0},
    "AUTO":      {"display_name": "Rovexa Auto",      "base_fare": 30, "rate_per_km": 12, "rate_per_min": 1.5, "night_pct": 20, "airport": 50, "surge": 1.0},
    "MINI":      {"display_name": "Rovexa Mini",      "base_fare": 40, "rate_per_km": 15, "rate_per_min": 2.0, "night_pct": 20, "airport": 50, "surge": 1.0},
    "HATCHBACK": {"display_name": "Rovexa Hatchback", "base_fare": 35, "rate_per_km": 13, "rate_per_min": 1.5, "night_pct": 20, "airport": 50, "surge": 1.0},
    "SEDAN":     {"display_name": "Rovexa Sedan",     "base_fare": 50, "rate_per_km": 18, "rate_per_min": 2.5, "night_pct": 20, "airport": 50, "surge": 1.0},
    "SUV":       {"display_name": "Rovexa SUV",       "base_fare": 80, "rate_per_km": 25, "rate_per_min": 3.5, "night_pct": 20, "airport": 50, "surge": 1.0},
    "PREMIUM":   {"display_name": "Rovexa Premium",   "base_fare": 120, "rate_per_km": 35, "rate_per_min": 5.0, "night_pct": 20, "airport": 50, "surge": 1.0},
    "LUXURY":    {"display_name": "Rovexa Luxury",    "base_fare": 150, "rate_per_km": 45, "rate_per_min": 6.0, "night_pct": 20, "airport": 50, "surge": 1.0},
    "ELECTRIC":  {"display_name": "Rovexa EV",        "base_fare": 45, "rate_per_km": 14, "rate_per_min": 2.0, "night_pct": 20, "airport": 50, "surge": 1.0},
}


def seed_default_pricing_rules():
    """Ensure database has default pricing rules for all 5 vehicle types."""
    for v_type, data in DEFAULT_RULES.items():
        PricingRule.objects.get_or_create(
            vehicle_type=v_type,
            defaults={
                "display_name": data["display_name"],
                "base_fare": Decimal(str(data["base_fare"])),
                "rate_per_km": Decimal(str(data["rate_per_km"])),
                "rate_per_min": Decimal(str(data["rate_per_min"])),
                "night_charge_percent": Decimal(str(data["night_pct"])),
                "airport_flat_charge": Decimal(str(data["airport"])),
                "surge_multiplier": Decimal(str(data["surge"])),
                "is_active": True,
            }
        )


def get_pricing_rule(vehicle_type: str) -> PricingRule:
    """Retrieve active pricing rule for a vehicle type or return fallback."""
    v_type = vehicle_type.upper()
    try:
        rule = PricingRule.objects.get(vehicle_type=v_type, is_active=True)
        return rule
    except PricingRule.DoesNotExist:
        # Fallback to default dictionary values
        seed_default_pricing_rules()
        return PricingRule.objects.filter(vehicle_type=v_type).first()


def calculate_surge_multiplier(pickup_address: str = "", drop_address: str = "", now=None) -> tuple[Decimal, list[str]]:
    """
    Evaluates dynamic surge multiplier based on peak hours and conditions.
    Returns: (surge_multiplier: Decimal, reasons: list[str])
    """
    if now is None:
        now = timezone.now()

    reasons = []
    multiplier = Decimal("1.0")

    # Local hour check
    hour = now.hour

    # Morning Peak Hours (8:00 AM to 10:30 AM)
    if 8 <= hour < 11:
        multiplier += Decimal("0.25")
        reasons.append("Morning Rush Hour (1.25x)")
    # Evening Peak Hours (5:00 PM to 8:30 PM)
    elif 17 <= hour < 21:
        multiplier += Decimal("0.35")
        reasons.append("Evening Peak Demand (1.35x)")

    # Cap surge between 1.0x and 2.5x
    if multiplier > Decimal("2.5"):
        multiplier = Decimal("2.5")

    return multiplier, reasons


def calculate_trip_fare(
    vehicle_type: str,
    distance_km: float,
    duration_mins: int = 15,
    pickup_address: str = "",
    drop_address: str = "",
    coupon_code: str = "",
    custom_surge: float = None,
    booking_category: str = "DAILY_RIDE",
    rental_package: str = "",
    outstation_type: str = "ONE_WAY",
) -> dict:
    """
    Calculates detailed fare breakdown according to Rovexa dynamic pricing formula.
    Supports DAILY_RIDE, SCHEDULED, RENTAL, and OUTSTATION categories.
    """
    dist_val = max(0.0, float(distance_km or 0))
    dist = Decimal(str(dist_val))

    # Calculate realistic duration based on distance if default duration is too low
    est_dur = max(int(duration_mins or 0), max(5, int(dist_val * 1.5)))
    dur  = Decimal(str(est_dur))

    rule = get_pricing_rule(vehicle_type)
    rule_base     = Decimal(str(rule.base_fare if rule else DEFAULT_RULES.get(vehicle_type.upper(), {}).get("base_fare", 40)))
    rate_per_km   = Decimal(str(rule.rate_per_km if rule else DEFAULT_RULES.get(vehicle_type.upper(), {}).get("rate_per_km", 15)))
    rate_per_min  = Decimal(str(rule.rate_per_min if rule else DEFAULT_RULES.get(vehicle_type.upper(), {}).get("rate_per_min", 2)))
    rule_surge    = Decimal(str(rule.surge_multiplier if rule else 1.0))

    if booking_category == "RENTAL":
        # Rental packages: 2_HRS_20_KM (₹499), 4_HRS_40_KM (₹899), 8_HRS_80_KM (₹1799)
        if "2" in rental_package:
            base_fare = Decimal("499.00")
            included_km = 20.0
        elif "4" in rental_package:
            base_fare = Decimal("899.00")
            included_km = 40.0
        else:  # 8 HRS 80 KM
            base_fare = Decimal("1799.00")
            included_km = 80.0

        extra_km = max(0.0, distance_km - included_km)
        distance_fare = Decimal(str(extra_km)) * Decimal("18.00")
        time_fare = Decimal("0.00")
        subtotal = base_fare + distance_fare

    elif booking_category == "OUTSTATION":
        # Outstation: Min 250 km / day + ₹300 Driver Allowance / Day
        billable_km = max(250.0, distance_km)
        rate_outstation = Decimal("16.00") if outstation_type == "ONE_WAY" else Decimal("14.00")
        distance_fare = Decimal(str(billable_km)) * rate_outstation
        base_fare = Decimal("300.00")  # Driver Allowance
        time_fare = Decimal("0.00")
        subtotal = base_fare + distance_fare

    else:
        # Standard Daily Ride or Scheduled Ride
        base_fare     = rule_base
        distance_fare = dist * rate_per_km
        time_fare     = dur * rate_per_min
        subtotal      = base_fare + distance_fare + time_fare

    # Evaluate dynamic surge
    dynamic_surge, surge_reasons = calculate_surge_multiplier(pickup_address, drop_address)
    surge_multiplier = Decimal(str(custom_surge)) if custom_surge is not None else max(rule_surge, dynamic_surge)

    # Night Surcharge Check (10 PM to 5 AM)
    now = timezone.now()
    is_night = (now.hour >= 22 or now.hour < 5)
    night_charge = Decimal("0")
    if is_night:
        night_pct = Decimal(str(rule.night_charge_percent if rule else 20))
        night_charge = (subtotal * night_pct) / Decimal("100")
        surge_reasons.append("Night Charge (+20%)")

    # Airport Flat Surcharge
    is_airport = "airport" in pickup_address.lower() or "airport" in drop_address.lower()
    airport_charge = Decimal("0")
    if is_airport:
        airport_charge = Decimal(str(rule.airport_flat_charge if rule else 50))
        surge_reasons.append("Airport Pickup/Drop (+₹50)")

    gross_fare = (subtotal * surge_multiplier) + night_charge + airport_charge

    # Coupon Discount Engine
    discount_amount = Decimal("0")
    applied_coupon  = None
    coupon_error    = None

    if coupon_code:
        try:
            cp = Coupon.objects.get(code__iexact=coupon_code.strip(), is_active=True)
            if cp.valid_until and cp.valid_until < now:
                coupon_error = "Coupon has expired."
            elif cp.uses_count >= cp.max_uses:
                coupon_error = "Coupon usage limit reached."
            elif gross_fare < cp.min_trip_fare:
                coupon_error = f"Minimum fare ₹{cp.min_trip_fare} required for this coupon."
            else:
                calculated_discount = (gross_fare * cp.discount_percent) / Decimal("100")
                discount_amount     = min(calculated_discount, cp.max_discount_amount)
                applied_coupon      = cp.code
        except Coupon.DoesNotExist:
            coupon_error = "Invalid promo code."

    final_total = max(Decimal("30.00"), gross_fare - discount_amount)

    return {
        "vehicle_type":           vehicle_type.upper(),
        "base_fare":              round(float(base_fare), 2),
        "distance_fare":          round(float(distance_fare), 2),
        "time_fare":              round(float(time_fare), 2),
        "subtotal":               round(float(subtotal), 2),
        "surge_multiplier":       round(float(surge_multiplier), 2),
        "surge_reasons":          surge_reasons,
        "is_night":               is_night,
        "night_charge":           round(float(night_charge), 2),
        "is_airport":             is_airport,
        "airport_charge":         round(float(airport_charge), 2),
        "gross_fare":             round(float(gross_fare), 2),
        "discount_amount":        round(float(discount_amount), 2),
        "coupon_code":            applied_coupon or "",
        "coupon_error":           coupon_error,
        "total_fare":             round(float(final_total), 2),
    }
