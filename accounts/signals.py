"""
accounts/signals.py
───────────────────
Sends admin notification whenever:
  • A new customer registers / account is created
  • An existing customer logs in
"""

from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="accounts.CustomUser")
def on_customer_registered(sender, instance, created, **kwargs):
    """Fire email + WhatsApp alert to admin when a new CUSTOMER account is created."""
    try:
        if created and getattr(instance, "role", "") == "CUSTOMER":
            from notifications.sender import notify_customer_registered
            notify_customer_registered(instance)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"[Registration Signal] Failed: {exc}")


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

