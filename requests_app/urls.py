from django.urls import path
from . import views

urlpatterns = [
    # Admin management
    path("admin-panel/",                  views.admin_dashboard_redirect, name="admin_panel_index"),
    path("admin-panel/users/",            views.admin_users,              name="admin_users"),
    path("admin-panel/users/<str:user_id>/edit/", views.admin_user_edit,  name="admin_user_edit"),
    path("admin-panel/users/<str:user_id>/toggle-status/", views.admin_user_toggle_status, name="admin_user_toggle_status"),
    path("admin-panel/users/<str:user_id>/delete/", views.admin_user_delete, name="admin_user_delete"),
    path("admin-panel/reports/",          views.admin_reports_redirect, name="admin_reports_alias"),
    path("admin-panel/pricing/",          views.admin_pricing,           name="admin_pricing"),
    path("admin-panel/sos/",              views.admin_sos_alerts,        name="admin_sos_alerts"),
]
