from django import forms
from django.core.exceptions import ValidationError
from .models import Booking

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            "booking_category",
            "vehicle_type",
            "payment_method",
        ]
        widgets = {
            "booking_category": forms.Select(attrs={"class": "form-select"}),
            "vehicle_type": forms.Select(attrs={"class": "form-select"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_vehicle_type(self):
        vtype = self.cleaned_data.get("vehicle_type")
        valid_types = ["AUTO", "MINI", "HATCHBACK", "SEDAN", "SUV", "LUXURY", "PREMIUM"]
        if vtype and vtype.upper() not in valid_types:
            raise ValidationError(f"Invalid vehicle type '{vtype}'. Please select a valid cab option.")
        return vtype

    def clean_payment_method(self):
        method = self.cleaned_data.get("payment_method")
        valid_methods = ["CASH", "WALLET", "ONLINE", "Cash", "UPI", "Card", "Wallet", "Razorpay"]
        if method and method not in valid_methods:
            raise ValidationError(f"Invalid payment method '{method}'.")
        return method