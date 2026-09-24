"""
WSGI config for Rovexa project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Rovexa.settings")

application = get_wsgi_application()

from Rovexa.keep_alive import start_self_ping_worker
start_self_ping_worker()
