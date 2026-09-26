from django.apps import AppConfig


class BookingConfig(AppConfig):
    name = "booking"

    def ready(self):
        import booking.signals  # noqa: F401 — registers new booking & status-change signals
