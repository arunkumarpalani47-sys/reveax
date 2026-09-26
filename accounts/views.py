import re
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import CustomUser
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from .forms import UserProfileForm
# Rate limiting on login endpoints
from django_ratelimit.decorators import ratelimit


ALLOWED_SELF_REGISTER_ROLES = ("CUSTOMER",)


def validate_indian_mobile(phone_raw):
    """
    Validates and normalizes Indian mobile numbers.
    Returns: (cleaned_10_digit_str, error_message_str)
    """
    if not phone_raw or not phone_raw.strip():
        return None, "Mobile number is mandatory for creating a customer account."

    raw = phone_raw.strip()
    if re.search(r"[a-zA-Z]", raw):
        return None, "Mobile number cannot contain letters. Please enter digits only."

    digits = re.sub(r"\D", "", raw)

    # Normalize country code / leading zeros
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10:
        return None, "Please enter a valid 10-digit Indian mobile number (e.g. 9876543210)."

    if not re.match(r"^[6-9]\d{9}$", digits):
        return None, "Invalid Indian mobile number. Mobile numbers must start with 6, 7, 8, or 9 (e.g. 9876543210)."

    return digits, None


def register(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        ctx = {
            "next": next_url,
            "form_data": {
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
                "email": email,
                "phone": phone_raw,
            }
        }

        # 1. Phone number is mandatory & must be valid Indian mobile format
        clean_phone, phone_error = validate_indian_mobile(phone_raw)
        if phone_error:
            messages.error(request, phone_error)
            return render(request, "accounts/register.html", ctx)

        # 2. Check if mobile number is already in use
        if CustomUser.objects.filter(
            Q(phone=clean_phone) | Q(phone=f"+91{clean_phone}") | Q(phone=f"91{clean_phone}") | Q(phone__endswith=clean_phone)
        ).exists():
            messages.error(request, f"An account with mobile number {clean_phone} already exists. Please sign in or use another number.")
            return render(request, "accounts/register.html", ctx)

        # 3. Check other required fields
        if not first_name:
            messages.error(request, "First name is required.")
            return render(request, "accounts/register.html", ctx)

        if not last_name:
            messages.error(request, "Last name is required.")
            return render(request, "accounts/register.html", ctx)

        if not username:
            messages.error(request, "Username is required.")
            return render(request, "accounts/register.html", ctx)

        if not email:
            messages.error(request, "Email address is required.")
            return render(request, "accounts/register.html", ctx)

        if not password or not confirm_password:
            messages.error(request, "Password and confirm password are required.")
            return render(request, "accounts/register.html", ctx)

        # 4. Check Password Match & Length
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/register.html", ctx)

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, "accounts/register.html", ctx)

        # 5. Check Username uniqueness
        if CustomUser.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already exists. Please choose a different one.")
            return render(request, "accounts/register.html", ctx)

        # 6. Check Email uniqueness
        if CustomUser.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists. Please log in or use another email.")
            return render(request, "accounts/register.html", ctx)

        # Check if email, phone, or username belongs to a blocked account
        blocked_user = CustomUser.objects.filter(
            Q(email__iexact=email) | Q(phone=clean_phone) | Q(username__iexact=username),
            is_active=False
        ).first()
        if blocked_user:
            messages.error(
                request,
                f"🚫 The account associated with '{email}' has been BLOCKED by the administrator. Registration and login are forbidden."
            )
            return render(request, "accounts/register.html", ctx)

        # 7. Create User with role CUSTOMER and normalized phone stored
        user = CustomUser.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone=clean_phone,
            role="CUSTOMER",
            password=password
        )
        user.save()

        # 8. Log in the newly registered customer immediately
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"🎉 Welcome to Rovexa Cab Services, {user.first_name}! You are registered and logged in.")

        if next_url:
            return redirect(next_url)
        return redirect("home")

    return render(request, "accounts/register.html", {"next": next_url, "form_data": {}})


# ─── Role portal (landing page — pick your role) ───────────────────────────
def login_portal(request):
    """Show the role-picker landing page."""
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    return render(request, "accounts/login_portal.html")


# ─── Admin login ─────────────────────────────────────────────────────────────────────────
# Rate limit: max 10 login attempts per IP per minute
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def admin_login(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Check if admin account is blocked
        matched_admin = CustomUser.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
        if matched_admin and not matched_admin.is_active:
            messages.error(
                request,
                f"🚫 Administrator account ({matched_admin.username}) has been BLOCKED or deactivated."
            )
            return render(request, "accounts/admin_login.html")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "🚫 This administrator account is blocked.")
                return render(request, "accounts/admin_login.html")

            if user.role == "ADMIN" or user.is_staff or user.is_superuser:
                login(request, user)
                return redirect("admin_dashboard")
            else:
                messages.error(request, "This portal is for Admins only. Please use the correct login.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/admin_login.html")


# ─── Customer login ───────────────────────────────────────────────────────────────────────
# Rate limit: max 10 login attempts per IP per minute
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def customer_login(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""

    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        return _redirect_by_role(request.user)

    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        matched_user = None

        # 1. Match by 10-digit mobile number
        clean_digits = re.sub(r"[^0-9]", "", identifier)
        if len(clean_digits) >= 10:
            phone_10 = clean_digits[-10:]
            matched_user = CustomUser.objects.filter(
                Q(phone=phone_10) |
                Q(phone=f"+91{phone_10}") |
                Q(phone=f"91{phone_10}") |
                Q(phone__endswith=phone_10)
            ).first()

        # 2. Match by email
        if matched_user is None and "@" in identifier:
            matched_user = CustomUser.objects.filter(email__iexact=identifier).first()

        # 3. Direct username match
        if matched_user is None:
            matched_user = CustomUser.objects.filter(username__iexact=identifier).first()

        # ⚠️ CRITICAL: Strict blocked user enforcement
        # If the account exists and is blocked (is_active=False), NEVER ALLOW LOGIN.
        if matched_user and not matched_user.is_active:
            user_label = matched_user.email or matched_user.phone or matched_user.username
            messages.error(
                request,
                f"🚫 Your account ({user_label}) has been BLOCKED by the administrator. Access is disabled for this email/account. Please contact support."
            )
            return render(request, "accounts/customer_login.html", {"next": next_url})

        # Attempt authentication using matched username or raw identifier
        auth_username = matched_user.username if matched_user else identifier
        user = authenticate(request, username=auth_username, password=password)

        if user is not None:
            if not user.is_active:
                user_label = user.email or user.phone or user.username
                messages.error(
                    request,
                    f"🚫 Your account ({user_label}) has been BLOCKED by the administrator. Login is not allowed."
                )
                return render(request, "accounts/customer_login.html", {"next": next_url})

            if user.role == "CUSTOMER" or user.is_staff or user.is_superuser:
                login(request, user)
                messages.success(request, f"Welcome back, {user.display_name}!")
                if next_url:
                    return redirect(next_url)
                return redirect("home")
            else:
                messages.error(request, "This portal is for Customers. Please use the Admin login.")
        else:
            messages.error(request, "Invalid mobile number/username or password.")

    return render(request, "accounts/customer_login.html", {"next": next_url})


# ─── Kept for backward compatibility (/login/ still works) ──────────────────
def user_login(request):
    return redirect("customer_login")


# ─── Logout ─────────────────────────────────────────────────────────────────
def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("customer_login")


# ─── Helper ─────────────────────────────────────────────────────────────────
def _redirect_by_role(user):
    if user.role == "ADMIN":
        return redirect("admin_dashboard")
    elif user.role == "CUSTOMER":
        return redirect("home")
    return redirect("home")


@login_required
def profile_view(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def settings_view(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep the user logged in
            messages.success(request, "Your password was successfully updated!")
            return redirect("settings")
        else:
            messages.error(request, "Please correct the error below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/settings.html", {"form": form})