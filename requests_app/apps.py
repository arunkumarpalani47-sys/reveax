from django.apps import AppConfig

class RequestsAppConfig(AppConfig):
    default_auto_field = "django_mongodb_backend.fields.ObjectIdAutoField"
    name = "requests_app"
