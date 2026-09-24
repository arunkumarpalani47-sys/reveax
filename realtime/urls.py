from django.urls import path
from . import views

app_name = "realtime"

urlpatterns = [
    path("api/nearby-drivers/",         views.api_nearby_drivers,         name="api_nearby_drivers"),
    path("api/driver/toggle/",          views.api_driver_toggle,          name="api_driver_toggle"),
    path("api/search-driver/",          views.api_search_driver,          name="api_search_driver"),
    path("api/booking/status/",         views.api_booking_status_update,  name="api_booking_status"),
    path("api/online-drivers/count/",   views.api_online_drivers_count,   name="api_online_count"),
]
