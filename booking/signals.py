"""
booking/signals.py
──────────────────
Sends admin notifications for:
  • New booking created (status = PENDING)
  • Booking status changed (any transition)
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


# ── store the old status before save so we can compare ──────────────────────
@receiver(pre_save, sender="booking.Booking")
def capture_old_booking_status(sender, instance, **kwargs):
    """Capture the current DB status before any save."""
    try:
        if instance.pk:
            old = sender.objects.get(pk=instance.pk)
            instance._old_status = old.status
        else:
            instance._old_status = None
    except Exception:
        instance._old_status = None


# ── after save: fire notifications ──────────────────────────────────────────
@receiver(post_save, sender="booking.Booking")
def on_booking_saved(sender, instance, created, **kwargs):
    """Send admin alert on new booking or status change."""
    try:
        from notifications.sender import notify_new_booking, notify_booking_status_change

        if created:
            # Brand-new booking
            notify_new_booking(instance)
        else:
            # Existing booking — check if status changed
            old_status = getattr(instance, "_old_status", None)
            new_status = instance.status
            if old_status and new_status and old_status != new_status:
                notify_booking_status_change(instance, old_status, new_status)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"[Booking Signal] Failed: {exc}")
