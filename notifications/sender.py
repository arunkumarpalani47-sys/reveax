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
    """Build a professional branded HTML email."""
    now_str = datetime.now().strftime("%d %b %Y  %I:%M %p")

    # Pick a lighter shade for the gradient
    gradients = {
        "#2563eb": "linear-gradient(135deg, #1e40af 0%, #2563eb 60%, #3b82f6 100%)",
        "#059669": "linear-gradient(135deg, #065f46 0%, #059669 60%, #10b981 100%)",
        "#7c3aed": "linear-gradient(135deg, #4c1d95 0%, #7c3aed 60%, #a78bfa 100%)",
    }
    gradient = gradients.get(color, f"linear-gradient(135deg, {color}, {color})")

    row_html = ""
    for i, (label, value) in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else "#f8faff"
        row_html += f"""
        <tr style="background:{bg};">
          <td style="padding:12px 20px;color:#64748b;font-size:13px;font-weight:600;
                     width:38%;border-bottom:1px solid #e2e8f0;letter-spacing:0.3px;">
            {label}
          </td>
          <td style="padding:12px 20px;color:#0f172a;font-size:13px;
                     border-bottom:1px solid #e2e8f0;font-weight:500;">
            {value or "—"}
          </td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef2f7;font-family:'Segoe UI',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f7;padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#ffffff;border-radius:16px;overflow:hidden;
              box-shadow:0 8px 32px rgba(0,0,0,0.10);max-width:600px;">

  <!-- ══ TOP BRAND BAR ══ -->
  <tr>
    <td style="background:#0f172a;padding:14px 28px;text-align:left;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <span style="color:#ffffff;font-size:20px;font-weight:900;
                         letter-spacing:2px;text-transform:uppercase;">ROVEAX</span>
            <span style="color:#94a3b8;font-size:11px;margin-left:8px;
                         font-weight:400;letter-spacing:1px;">CAB SERVICES</span>
          </td>
          <td align="right">
            <span style="color:#64748b;font-size:11px;">Admin Notification</span>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ══ GRADIENT HERO BANNER ══ -->
  <tr>
    <td style="background:{gradient};padding:36px 28px 28px;">
      <table cellpadding="0" cellspacing="0">
        <tr>
          <td style="vertical-align:middle;padding-right:18px;">
            <div style="background:rgba(255,255,255,0.18);border-radius:50%;
                        width:64px;height:64px;text-align:center;line-height:64px;
                        font-size:30px;border:2px solid rgba(255,255,255,0.3);">
              {icon}
            </div>
          </td>
          <td style="vertical-align:middle;">
            <div style="color:rgba(255,255,255,0.75);font-size:11px;
                        letter-spacing:2px;text-transform:uppercase;
                        font-weight:600;margin-bottom:6px;">
              Automated Alert
            </div>
            <div style="color:#ffffff;font-size:20px;font-weight:800;
                        line-height:1.3;letter-spacing:0.2px;">
              {title}
            </div>
            <div style="color:rgba(255,255,255,0.65);font-size:12px;margin-top:6px;">
              🕐 {now_str} &nbsp;|&nbsp; 📍 Roveax Admin Panel
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ══ DIVIDER ACCENT ══ -->
  <tr>
    <td style="height:4px;background:{gradient};"></td>
  </tr>

  <!-- ══ SECTION LABEL ══ -->
  <tr>
    <td style="padding:20px 20px 4px;">
      <span style="background:#f1f5f9;color:#475569;font-size:11px;font-weight:700;
                   padding:4px 12px;border-radius:20px;letter-spacing:1px;
                   text-transform:uppercase;border:1px solid #e2e8f0;">
        &nbsp;Details
      </span>
    </td>
  </tr>

  <!-- ══ DATA TABLE ══ -->
  <tr>
    <td style="padding:8px 20px 20px;">
      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-radius:10px;overflow:hidden;
                    border:1px solid #e2e8f0;">
        {row_html}
      </table>
    </td>
  </tr>

  <!-- ══ ACTION BUTTON ══ -->
  <tr>
    <td style="padding:4px 20px 28px;text-align:center;">
      <a href="https://reveax.onrender.com/admin/"
         style="display:inline-block;background:{gradient};
                color:#ffffff;font-size:14px;font-weight:700;
                padding:14px 36px;border-radius:50px;text-decoration:none;
                letter-spacing:0.5px;box-shadow:0 4px 15px rgba(0,0,0,0.2);">
        Open Admin Panel →
      </a>
    </td>
  </tr>

  <!-- ══ FOOTER ══ -->
  <tr>
    <td style="background:#0f172a;padding:20px 28px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="color:#94a3b8;font-size:12px;line-height:1.8;">
            <strong style="color:#e2e8f0;">Roveax Cab Services</strong><br>
            📞 +91 94873 51101 &nbsp;|&nbsp;
            🌐 reveax.onrender.com<br>
            <span style="color:#64748b;font-size:11px;">
              This is an automated notification — do not reply to this email.
            </span>
          </td>
          <td align="right" style="vertical-align:top;">
            <span style="color:#1e40af;font-size:22px;font-weight:900;
                         letter-spacing:2px;">R</span>
            <span style="color:#64748b;font-size:10px;display:block;
                         text-align:right;letter-spacing:1px;">ROVEAX</span>
          </td>
        </tr>
      </table>
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
