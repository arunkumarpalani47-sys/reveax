"""
accounts/signals.py
───────────────────
Sends admin notification whenever a customer logs in.
"""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def on_customer_login(sender, request, user, **kwargs):
    """Fire email + WhatsApp alert to admin when a CUSTOMER logs in."""
    try:
        if getattr(user, "role", "") == "CUSTOMER":
            from notifications.sender import notify_customer_login
            notify_customer_login(user)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"[Login Signal] Failed: {exc}")
