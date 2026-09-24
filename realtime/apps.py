from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"
    name = "realtime"
    verbose_name = "Real-Time Engine"
