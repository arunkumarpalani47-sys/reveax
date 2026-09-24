from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("api/stats/", views.api_stats, name="api_stats"),
    path("services/", views.services, name="services"),
    path("contact/", views.contact, name="contact"),
]