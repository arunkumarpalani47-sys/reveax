from django.urls import path
from . import views

urlpatterns = [
    path("", views.booking_list, name="booking_list"),
    path("add/", views.add_booking, name="add_booking"),
    path("detail/<str:id>/", views.booking_detail, name="booking_detail"),
    path("<str:id>/accept/", views.accept_booking, name="accept_booking"),
    path("<str:id>/reject/", views.reject_booking, name="reject_booking"),
    path("edit/<str:id>/", views.edit_booking, name="edit_booking"),
    path("delete/<str:id>/", views.delete_booking, name="delete_booking"),
    path(
        "search/",
        views.search_vehicle,
        name="search_vehicle"
    ),

    path("track/<str:id>/", views.booking_track, name="booking_track"),
    path("driver-console/<str:id>/", views.driver_console, name="driver_console"),
    path("cancel/<str:id>/", views.cancel_booking, name="cancel_booking"),

    # Sprint 2 APIs
    path("api/create/", views.api_create_booking, name="api_create_booking"),
    path("api/verify-otp/", views.api_verify_otp, name="api_verify_otp"),
    path("api/complete-trip/", views.api_complete_trip, name="api_complete_trip"),
    path("api/driver-respond/", views.api_driver_respond, name="api_driver_respond"),

    # Sprint 4 Pricing APIs
    path("api/calculate-fare/", views.api_calculate_fare, name="api_calculate_fare"),
    path("api/apply-coupon/", views.api_apply_coupon, name="api_apply_coupon"),

    # Sprint 6 Rating API
    path("api/rate-driver/", views.api_rate_driver, name="api_rate_driver"),

    # Sprint 7 Safety & SOS APIs
    path("track/share/<str:share_token>/", views.public_track_ride, name="public_track_ride"),
    path("api/sos/", views.api_trigger_sos, name="api_trigger_sos"),

    # Sprint 9 Next-Gen Booking APIs
    path("api/split-fare/", views.api_split_fare, name="api_split_fare"),
    path("calendar/ics/<str:id>/", views.download_calendar_ics, name="download_calendar_ics"),
    path("api/favorite-driver/", views.api_toggle_favorite_driver, name="api_toggle_favorite_driver"),
    path("api/nearby-drivers/", views.api_nearby_drivers, name="api_nearby_drivers"),

    # Live Passenger-Driver Chat & Realtime Status APIs
    path("api/chat/send/", views.api_send_chat, name="api_send_chat"),
    path("api/chat/messages/<str:booking_id>/", views.api_get_chat_messages, name="api_get_chat_messages"),
    path("api/chat/get/<str:booking_id>/", views.api_get_chat_messages, name="api_get_chat_messages_alt"),
    path("api/status/<str:booking_id>/", views.api_booking_status, name="api_booking_status"),
]