from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Main customer login (Direct access - no entry/portal screen)
    path("login/", views.customer_login, name="login"),
    path("login/customer/", views.customer_login, name="customer_login"),

    # Admin Login (Dedicated URL)
    path("login/admin/", views.admin_login, name="admin_login"),

    # Role portal (kept at /portal/ if needed, but not in customer flow)
    path("portal/", views.login_portal, name="login_portal"),

    # Registration (Customer only; Partners created by Admin)
    path("register/", views.register, name="register"),
    path("register/customer/", views.register, name="customer_register"),

    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),

    # Password Reset Flow
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/password_reset_email.html",
        subject_template_name="accounts/password_reset_subject.txt"
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"
    ), name="password_reset_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html"
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"
    ), name="password_reset_complete"),

    path("logout/", views.user_logout, name="logout"),
]