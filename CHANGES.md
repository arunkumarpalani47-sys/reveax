# Rovexa — Rebuild Summary

This is your project rebuilt around a clean **3-role system**: **Admin**,
**Partner**, **Customer**. Every bug found in the original review has been
fixed and verified with an automated smoke test across all three roles.

## Role model

- **Admin** — full visibility and control over everything (bookings,
  drivers, vehicles, payments, users).
- **Partner** — merges the old "Owner" and "Driver" roles. A Partner owns
  vehicles, manages their own drivers, and can optionally link a driver's
  own login so that driver can log in and manage their assigned rides
  directly (`driver.user` field).
- **Customer** — books rides, views/pays for their own bookings only.

The old 5-role system (Admin/Customer/Owner/Driver/Partner) and the empty
`owner` app have been removed entirely.

## Bugs fixed

1. **11 templates with broken HTML** — `{% extends %}` was wrapped inside
   a leftover `<html><head><body>` skeleton, causing Django to silently
   render two nested HTML documents. This was the #1 cause of your
   alignment/spacing issues. All 11 are now clean single-document templates.
2. **Fragile sidebar layout** — `base.html` used to decide whether to show
   the sidebar by string-matching `request.path` against a hardcoded list,
   which is why the customer dashboard had no sidebar. First attempted a
   `{% block use_sidebar %}yes{% endblock %}` flag checked via
   `{{ self.use_sidebar }}`, but that pattern turned out to be unreliable
   in Django's template engine (confirmed via preview screenshots — the
   Partner dashboard rendered with no sidebar at all). Replaced with the
   standard, reliable Django pattern: a `dashboard_base.html` that extends
   `base.html` and overrides `{% block layout %}` with the sidebar grid.
   Every dashboard/CRUD page now extends `dashboard_base.html` instead of
   `base.html` directly — no runtime flag-checking involved.
3. **Role-aware sidebar** — customers no longer see admin-only links like
   "Drivers"/"Vehicles"; each role sees only what's relevant to them.
4. **Crash bug** — `Driver.user` was defined outside the model class
   (dead code). Fixed and properly linked as a `OneToOneField`, so
   `request.user.driver_profile` now works instead of crashing.
5. **Form validation order bug** — Partner-only forms (vehicle, driver)
   were popping the `owner`/`partner` field only on GET, so POST
   submissions always failed validation silently. Fixed with a shared
   `_build_form()` helper that pops the field consistently.
6. **Duplicate `vehicle_list()`** — was defined 3 times; only the last one
   ran. Cleaned up to a single implementation.
7. **Unreachable `booking_detail`** — view existed with no URL and no
   template. Now wired up with a real detail page and ownership checks.
8. **Duplicate `home` route** — `home.urls` and `accounts.urls` both
   defined `""`. Removed the duplicate.
9. **Duplicate pickup/drop form fields** — the map picker's hidden inputs
   shared the same `name` as the ModelForm's fields, causing unpredictable
   submitted values. Fixed by excluding them from the ModelForm.

## Access control added

- Every view now requires login; role-specific views require the correct
  role (`@role_required("ADMIN", "PARTNER")` etc. via a new
  `accounts/decorators.py`).
- **Partners only see their own** vehicles, drivers, bookings, and
  payments — never another partner's data.
- **Customers only see their own** bookings and payments.
- Destructive actions (delete) now require POST with CSRF protection and
  a confirmation step, not a bare `<a href>` GET link.
- Registration form can no longer be used to create an Admin account.

## New/completed features

- **Partner dashboard** — real stats (vehicle/driver counts, pending vs.
  completed bookings, total earnings) instead of a placeholder `<h1>`.
- **Booking detail page** — built from scratch, with role-based access.
- **Driver ride actions** (accept/start/complete) converted from GET
  links to CSRF-protected POST forms.
- Registration now validates required fields and enforces an 8-character
  minimum password.

## Verified working (automated test)

Every page was smoke-tested end-to-end as Admin, Partner, and Customer:
login → dashboard → add/edit vehicle → add/edit driver → book a ride →
view booking detail → make payment. **0 failures.** Cross-role access
(e.g. Customer trying to reach `/vehicle/`) correctly returns 403.

## About MongoDB

Kept on a relational database (SQLite for dev, easy to point at
PostgreSQL/MySQL for production via `DATABASE_URL`). This app is
fundamentally relational — bookings join customers, vehicles, drivers,
and payments constantly — and Django's ORM, admin, and auth system are
all built around that. Switching to MongoDB (via Djongo or
django-mongodb-backend) would mean fighting the ORM for no real benefit.
If your MySQL setup was the actual pain point, PostgreSQL or SQLite are
much smaller, safer changes and both are already wired up.

## Running it

```bash
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python create_admin.py     # creates the admin login
python manage.py runserver
```

## Still worth doing (not in this pass)

- Real payment gateway integration (Razorpay/Stripe) — currently marks
  payments "Paid" immediately on submit, with no actual charge.
- Email/OTP verification and password reset flow.
- Automated tests (`tests.py` files are still empty stubs).
- Ride cancellation flow for customers.
