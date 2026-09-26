from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from accounts.decorators import role_required
from accounts.models import CustomUser


def admin_dashboard_redirect(request):
    return redirect("/dashboard/")


def admin_reports_redirect(request):
    return redirect("/dashboard/reports/")


# ── Admin management views ────────────────────────────────────────────────────

@role_required("ADMIN")
def admin_users(request):
    role_filter = request.GET.get("role", "all").upper()
    search = request.GET.get("q", "") or request.GET.get("search", "")
    qs = CustomUser.objects.all().order_by("-date_joined")
    if role_filter == "BLOCKED":
        qs = qs.filter(is_active=False)
    elif role_filter and role_filter != "ALL":
        qs = qs.filter(role__iexact=role_filter)
    if search:
        search_lower = search.lower().strip()
        qs = [
            u for u in qs
            if search_lower in (u.username or "").lower()
            or search_lower in (u.email or "").lower()
            or search_lower in (u.phone or "").lower()
            or search_lower in (u.get_full_name() or "").lower()
        ]
    return render(request, "requests_app/admin_users.html", {
        "users": qs,
        "role_filter": role_filter.lower(),
        "search": search,
    })


@role_required("ADMIN")
def admin_user_edit(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == "POST":
        new_role = request.POST.get("new_role") or request.POST.get("role")
        if new_role in ["CUSTOMER", "ADMIN"]:
            user.role = new_role
            if new_role == "CUSTOMER":
                user.is_staff = False
                user.is_superuser = False
            elif new_role == "ADMIN":
                user.is_staff = True
                user.is_superuser = True
            user.save()
            messages.success(request, f"Successfully updated role for {user.username} to {new_role}.")
    return redirect("admin_users")


@role_required("ADMIN")
def admin_user_toggle_status(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.user.id == user.id:
        messages.error(request, "You cannot block your own admin account while logged in.")
        return redirect("admin_users")

    if request.method == "POST":
        user.is_active = not user.is_active
        user.save()
        if not user.is_active:
            messages.warning(
                request,
                f"🚫 User '{user.display_name}' ({user.email or user.username}) has been BLOCKED. They will never be allowed to log in."
            )
        else:
            messages.success(
                request,
                f"✅ User '{user.display_name}' ({user.email or user.username}) has been UNBLOCKED and activated."
            )
    return redirect("admin_users")


@role_required("ADMIN")
def admin_user_delete(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.user.id == user.id:
        messages.error(request, "You cannot delete your own admin account while logged in.")
        return redirect("admin_users")

    if request.method == "POST":
        uname = user.username
        uemail = user.email or user.phone or "account"
        user.delete()
        messages.success(request, f"🗑️ User '{uname}' ({uemail}) has been permanently deleted.")
    return redirect("admin_users")


from booking.models import PricingRule, Coupon
from booking.pricing import seed_default_pricing_rules

@role_required("ADMIN")
def admin_pricing(request):
    seed_default_pricing_rules()

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_rule":
            rule_id = request.POST.get("rule_id")
            rule = get_object_or_404(PricingRule, id=rule_id)
            rule.base_fare = request.POST.get("base_fare", rule.base_fare)
            rule.rate_per_km = request.POST.get("rate_per_km", rule.rate_per_km)
            rule.rate_per_min = request.POST.get("rate_per_min", rule.rate_per_min)
            rule.surge_multiplier = request.POST.get("surge_multiplier", rule.surge_multiplier)
            rule.night_charge_percent = request.POST.get("night_charge_percent", rule.night_charge_percent)
            rule.airport_flat_charge = request.POST.get("airport_flat_charge", rule.airport_flat_charge)
            rule.is_active = request.POST.get("is_active") == "on"
            rule.save()
            messages.success(request, f"Updated pricing rule for {rule.display_name}")

        elif action == "add_coupon":
            code = request.POST.get("code", "").strip().upper()
            pct = request.POST.get("discount_percent", 10)
            max_amt = request.POST.get("max_discount_amount", 100)
            min_fare = request.POST.get("min_trip_fare", 0)
            if code:
                Coupon.objects.create(
                    code=code,
                    discount_percent=pct,
                    max_discount_amount=max_amt,
                    min_trip_fare=min_fare,
                    is_active=True
                )
                messages.success(request, f"Added promo coupon {code}")

        elif action == "toggle_coupon":
            coupon_id = request.POST.get("coupon_id")
            cp = get_object_or_404(Coupon, id=coupon_id)
            cp.is_active = not cp.is_active
            cp.save()
            messages.success(request, f"Coupon {cp.code} status updated.")

        return redirect("admin_pricing")

    rules = PricingRule.objects.all().order_by("id")
    coupons = Coupon.objects.all().order_by("-created_at")

    return render(request, "requests_app/admin_pricing.html", {
        "rules": rules,
        "coupons": coupons,
    })


@role_required("ADMIN")
def admin_sos_alerts(request):
    """
    Admin Emergency SOS Operations Center.
    """
    from booking.models import EmergencyAlert

    if request.method == "POST":
        alert_id = request.POST.get("alert_id")
        alert = get_object_or_404(EmergencyAlert, id=alert_id)
        alert.status = "RESOLVED"
        alert.save()
        messages.success(request, f"Emergency SOS Alert #{alert.id} marked as RESOLVED.")
        return redirect("admin_sos_alerts")

    alerts = EmergencyAlert.objects.all().order_by("-created_at")
    active_count = EmergencyAlert.objects.filter(status="ACTIVE").count()

    return render(request, "requests_app/admin_sos.html", {
        "alerts": alerts,
        "active_count": active_count,
    })



