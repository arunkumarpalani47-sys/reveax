"""
Rovexa Security Headers Middleware
===================================
Adds Content-Security-Policy (CSP) and Permissions-Policy headers to every
HTTP response. These headers are not provided by Django out-of-the-box.

Fixes:
  V-07 — Missing Content-Security-Policy header
  V-11 — Missing Permissions-Policy header
"""


class SecurityHeadersMiddleware:
    """
    Injects CSP and Permissions-Policy headers into every HTTP response.
    Safe for both development (HTTP) and production (HTTPS).
    """

    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "font-src 'self' https: data: blob:; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https: wss: ws:; "
        "frame-src 'self' https:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self' https:; "
    )

    PERMISSIONS_POLICY = (
        "camera=(), "
        "microphone=(), "
        "geolocation=(self), "
        "payment=(self), "
        "usb=(), "
        "fullscreen=(self), "
        "autoplay=()"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Content-Security-Policy
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = self.CSP_POLICY

        # Permissions-Policy
        if "Permissions-Policy" not in response:
            response["Permissions-Policy"] = self.PERMISSIONS_POLICY

        # X-Permitted-Cross-Domain-Policies
        if "X-Permitted-Cross-Domain-Policies" not in response:
            response["X-Permitted-Cross-Domain-Policies"] = "none"

        return response


class BlockedUserMiddleware:
    """
    Instantly terminates the session of any currently active user if an Admin blocks or deactivates them.
    Prevents blocked customers from performing any action or remaining logged in.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "user", None) and request.user.is_authenticated:
            if not request.user.is_active:
                from django.contrib.auth import logout
                from django.contrib import messages
                from django.shortcuts import redirect
                logout(request)
                messages.error(
                    request,
                    "🚫 Your account has been BLOCKED by the administrator. Access is disabled."
                )
                return redirect("customer_login")

        return self.get_response(request)
