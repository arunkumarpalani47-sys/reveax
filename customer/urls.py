from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.customer_dashboard, name="customer_dashboard"),
]