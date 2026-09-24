"""
Shared access-control decorators.

role_required(*roles) ensures the logged-in user's role is one of the
given roles (e.g. "ADMIN", "PARTNER", "CUSTOMER"). Unauthenticated users
are sent to login; authenticated users with the wrong role get a 403.
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied(
                    "You do not have permission to access this page."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
