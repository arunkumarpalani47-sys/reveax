"""
WebSocket URL routing for Rovexa realtime engine.

Consumers:
  - LocationConsumer   → ws/location/      (driver sends GPS every 3s)
  - BookingConsumer    → ws/booking/<id>/  (customer listens to ride status)
  - DriverConsumer     → ws/driver/        (driver receives ride requests)
"""

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/location/$",                consumers.LocationConsumer.as_asgi()),
    re_path(r"ws/booking/(?P<booking_id>[^/]+)/$", consumers.BookingConsumer.as_asgi()),
    re_path(r"ws/driver/$",                  consumers.DriverConsumer.as_asgi()),
    re_path(r"ws/ride-request/(?P<booking_id>[^/]+)/$", consumers.RideRequestConsumer.as_asgi()),
    re_path(r"ws/wallet/$",                  consumers.WalletConsumer.as_asgi()),
]
