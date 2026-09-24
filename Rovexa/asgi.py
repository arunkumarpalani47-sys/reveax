"""
ASGI config for Rovexa project — Django Channels enabled.
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rovexa.settings")

django_asgi_app = get_asgi_application()

from realtime import routing  # noqa: E402 — must be after setup
from Rovexa.keep_alive import start_self_ping_worker

start_self_ping_worker()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(routing.websocket_urlpatterns)
        )
    ),
})
