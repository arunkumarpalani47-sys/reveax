"""
Rovexa Admin Notification Sender
=================================
Sends Email + WhatsApp alerts to admin when:
  - A customer logs in
  - A new booking is placed
  - A booking status changes

Email: via Gmail SMTP (configure EMAIL_HOST_USER / EMAIL_HOST_PASSWORD in .env)
WhatsApp: via Twilio WhatsApp API (configure TWILIO_* in .env)
         OR via wa.me link fallback for simple notification (no API needed).
"""

import logging
import threading
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Internal helper: fire-and-forget background thread so notifications never
# slow down the HTTP request/response cycle.
# ─────────────────────────────────────────────────────────────────────────────

def _run_in_thread(fn, *args, **kwargs):
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL NOTIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def _send_email_notification(subject: str, html_body: str):
    """Send an HTML email to the admin."""
    admin_email = getattr(settings, "ADMIN_NOTIFICATION_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    if not admin_email:
        logger.warning("[Rovexa Notifications] ADMIN_NOTIFICATION_EMAIL not set — skipping email.")
        return

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", f"Rovexa Cabs <{admin_email}>")

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=strip_tags(html_body),
            from_email=from_email,
            to=[admin_email],
        )
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"[Rovexa Notifications] Email sent to {admin_email}: {subject}")
    except Exception as exc:
        logger.error(f"[Rovexa Notifications] Email failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# WHATSAPP NOTIFICATION  (via Twilio)
# ─────────────────────────────────────────────────────────────────────────────

def _send_whatsapp_notification(message: str):
    """Send a WhatsApp message to admin via Twilio API."""
    account_sid  = getattr(settings, "TWILIO_ACCOUNT_SID", "")
    auth_token   = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    from_number  = getattr(settings, "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox default
    admin_number = getattr(settings, "ADMIN_WHATSAPP_NUMBER", "")

    if not all([account_sid, auth_token, admin_number]):
        logger.info("[Rovexa Notifications] Twilio credentials not set — skipping WhatsApp.")
        return

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        to_number = admin_number if admin_number.startswith("whatsapp:") else f"whatsapp:{admin_number}"
        msg = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        logger.info(f"[Rovexa Notifications] WhatsApp sent SID={msg.sid}")
    except ImportError:
        logger.warning("[Rovexa Notifications] twilio package not installed. Run: pip install twilio")
    except Exception as exc:
        logger.error(f"[Rovexa Notifications] WhatsApp failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# HTML EMAIL TEMPLATE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_email_html(title: str, color: str, icon: str, rows: list[tuple]) -> str:
    """Build a clean HTML email with a table of key-value rows."""
    now_str = datetime.now().strftime("%d %b %Y  %I:%M %p")
    row_html = ""
    for label, value in rows:
        row_html += f"""
        <tr>
          <td style="padding:10px 16px; color:#6b7280; font-size:13px; border-bottom:1px solid #f3f4f6; width:40%; font-weight:600;">{label}</td>
          <td style="padding:10px 16px; color:#111827; font-size:13px; border-bottom:1px solid #f3f4f6;">{value or '—'}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:24px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <!-- HEADER -->
        <tr>
          <td style="background:{color};padding:24px 28px;">
            <div style="font-size:28px;margin-bottom:4px;">{icon}</div>
            <div style="color:#ffffff;font-size:20px;font-weight:800;">{title}</div>
            <div style="color:rgba(255,255,255,0.8);font-size:12px;margin-top:4px;">{now_str} · Rovexa Cab Services</div>
          </td>
        </tr>
        <!-- DATA TABLE -->
        <tr>
          <td style="padding:8px 0;">
            <table width="100%" cellpadding="0" cellspacing="0">
              {row_html}
            </table>
          </td>
        </tr>
        <!-- FOOTER -->
        <tr>
          <td style="background:#f9fafb;padding:16px 28px;text-align:center;color:#9ca3af;font-size:11px;border-top:1px solid #f3f4f6;">
            This is an automated alert from <strong>Rovexa Cab Services</strong> admin dashboard.<br>
            <a href="https://reveax.onrender.com/admin/" style="color:#2563eb;">Open Admin Panel</a>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API: Trigger notifications
# ─────────────────────────────────────────────────────────────────────────────

def notify_customer_login(user):
    """Called when a customer logs in."""
    if not user or getattr(user, "role", "") != "CUSTOMER":
        return

    name  = getattr(user, "display_name", None) or user.get_full_name() or user.username
    email = user.email or "—"
    phone = getattr(user, "phone", None) or "—"
    now   = datetime.now().strftime("%d %b %Y  %I:%M %p")

    # Email
    subject   = f"🔔 Customer Login: {name}"
    html_body = _build_email_html(
        title=f"Customer Logged In — {name}",
        color="#2563eb",
        icon="🔔",
        rows=[
            ("Name",        name),
            ("Email",       email),
            ("Phone",       phone),
            ("Username",    user.username),
            ("Login Time",  now),
            ("Status",      "✅ Active Session"),
        ],
    )
    _run_in_thread(_send_email_notification, subject, html_body)

    # WhatsApp
    wa_msg = (
        f"🔔 *Rovexa – Customer Login Alert*\n\n"
        f"👤 *Name:* {name}\n"
        f"📧 *Email:* {email}\n"
        f"📞 *Phone:* {phone}\n"
        f"🕐 *Time:* {now}\n\n"
        f"_Customer is now browsing your platform._"
    )
    _run_in_thread(_send_whatsapp_notification, wa_msg)


def notify_new_booking(booking):
    """Called when a new booking is created (status=PENDING)."""
    try:
        customer = booking.customer
        name  = getattr(customer, "display_name", None) or customer.get_full_name() or customer.username
        email = customer.email or "—"
        phone = getattr(customer, "phone", None) or "—"
    except Exception:
        name = email = phone = "Unknown"

    now = datetime.now().strftime("%d %b %Y  %I:%M %p")
    bid = str(booking.id)[:8].upper()

    # Email
    subject   = f"🚖 New Booking #{bid} — {name}"
    html_body = _build_email_html(
        title=f"New Booking Received  #{bid}",
        color="#059669",
        icon="🚖",
        rows=[
            ("Booking ID",      bid),
            ("Customer Name",   name),
            ("Email",           email),
            ("Phone",           phone),
            ("Pickup",          getattr(booking, "pickup_location", "—")),
            ("Drop",            getattr(booking, "drop_location", "—")),
            ("Trip Type",       getattr(booking, "trip_type", "ONE_WAY")),
            ("Vehicle",         getattr(booking, "vehicle_type", "—")),
            ("Distance",        f"{booking.distance} km" if getattr(booking, "distance", None) else "—"),
            ("Total Fare",      f"₹{booking.total_fare}" if getattr(booking, "total_fare", None) else "—"),
            ("Status",          "⏳ Pending Admin Review"),
            ("Booked At",       now),
        ],
    )
    _run_in_thread(_send_email_notification, subject, html_body)

    # WhatsApp
    wa_msg = (
        f"🚖 *Rovexa – New Booking #{bid}*\n\n"
        f"👤 *Customer:* {name}\n"
        f"📞 *Phone:* {phone}\n"
        f"📧 *Email:* {email}\n"
        f"📍 *Pickup:* {getattr(booking, 'pickup_location', '—')}\n"
        f"🏁 *Drop:* {getattr(booking, 'drop_location', '—')}\n"
        f"🚗 *Vehicle:* {getattr(booking, 'vehicle_type', '—')}\n"
        f"📏 *Distance:* {getattr(booking, 'distance', '—')} km\n"
        f"💰 *Fare:* ₹{getattr(booking, 'total_fare', '—')}\n"
        f"🕐 *Time:* {now}\n\n"
        f"👉 Review at: https://reveax.onrender.com/admin/"
    )
    _run_in_thread(_send_whatsapp_notification, wa_msg)


def notify_booking_status_change(booking, old_status: str, new_status: str):
    """Called when a booking status changes."""
    status_icons = {
        "PENDING":         "⏳",
        "ACCEPTED":        "✅",
        "DRIVER_ASSIGNED": "🚗",
        "CONFIRMED":       "✅",
        "TRIP_STARTED":    "🟢",
        "TRIP_COMPLETED":  "🏁",
        "REJECTED":        "❌",
        "CANCELLED":       "🚫",
    }
    icon = status_icons.get(new_status, "🔄")

    try:
        customer = booking.customer
        name  = getattr(customer, "display_name", None) or customer.get_full_name() or customer.username
        phone = getattr(customer, "phone", None) or "—"
    except Exception:
        name = phone = "Unknown"

    now = datetime.now().strftime("%d %b %Y  %I:%M %p")
    bid = str(booking.id)[:8].upper()

    # Email
    subject   = f"{icon} Booking #{bid} → {new_status}"
    html_body = _build_email_html(
        title=f"Booking Status Changed  #{bid}",
        color="#7c3aed",
        icon=icon,
        rows=[
            ("Booking ID",    bid),
            ("Customer",      name),
            ("Phone",         phone),
            ("Previous Status", old_status),
            ("New Status",    f"{icon} {new_status}"),
            ("Pickup",        getattr(booking, "pickup_location", "—")),
            ("Drop",          getattr(booking, "drop_location", "—")),
            ("Total Fare",    f"₹{booking.total_fare}" if getattr(booking, "total_fare", None) else "—"),
            ("Changed At",    now),
        ],
    )
    _run_in_thread(_send_email_notification, subject, html_body)

    # WhatsApp
    wa_msg = (
        f"{icon} *Rovexa – Booking Status Update*\n\n"
        f"📋 *Booking ID:* #{bid}\n"
        f"👤 *Customer:* {name}  |  📞 {phone}\n"
        f"🔄 *Status:* {old_status} → *{new_status}*\n"
        f"💰 *Fare:* ₹{getattr(booking, 'total_fare', '—')}\n"
        f"🕐 *At:* {now}"
    )
    _run_in_thread(_send_whatsapp_notification, wa_msg)
