from django.shortcuts import render, redirect
from django.contrib import messages
from .models import CustomUser
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from .forms import UserProfileForm
# ✅ FIXED V-05: Rate limiting on login endpoints
from django_ratelimit.decorators import ratelimit


ALLOWED_SELF_REGISTER_ROLES = ("CUSTOMER",)


def register(request):

    if request.method == "POST":

        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        role = "CUSTOMER"
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        # Required fields
        if not all([first_name, last_name, username, email, password, confirm_password]):
            messages.error(request, "Please fill in all required fields.")
            return redirect("customer_register")

        # Check Password
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("customer_register")

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("customer_register")

        # Check Username
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("customer_register")

        # Check Email
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("customer_register")

        # Create User
        user = CustomUser.objects.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            phone=phone,
            role=role,
            password=password
        )

        user.save()

        messages.success(request, "Registration Successful! Please log in.")

        return redirect("customer_login")

    return render(request, "accounts/register.html")


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
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == "ADMIN":
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
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.role == "CUSTOMER":
                login(request, user)
                return redirect("home")
            else:
                messages.error(request, "This portal is for Customers only. Please use the correct login.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/customer_login.html")


# ─── Kept for backward compatibility (/login/ still works) ──────────────────
def user_login(request):
    return redirect("login_portal")


# ─── Logout ─────────────────────────────────────────────────────────────────
def user_logout(request):
    logout(request)
    return redirect("login_portal")


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