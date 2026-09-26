from django import forms
from django.core.exceptions import ValidationError
from .models import Booking

class BookingForm(forms.ModelForm):
    return_datetime = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"})
    )

    class Meta:
        model = Booking
        fields = [
            "booking_category",
            "vehicle_type",
            "payment_method",
            "trip_type",
            "return_datetime",
        ]
        widgets = {
            "booking_category": forms.Select(attrs={"class": "form-select"}),
            "vehicle_type": forms.Select(attrs={"class": "form-select"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "trip_type": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_vehicle_type(self):
        vtype = self.cleaned_data.get("vehicle_type") or "CAR_CAB"
        valid_types = ["CAR_CAB", "AUTO", "MINI", "HATCHBACK", "SEDAN", "SUV", "LUXURY", "PREMIUM"]
        if vtype.upper() not in valid_types:
            return "CAR_CAB"
        return vtype.upper()

    def clean_payment_method(self):
        method = self.cleaned_data.get("payment_method") or "CASH"
        valid_methods = ["CASH", "WALLET", "ONLINE", "Cash", "UPI", "Card", "Wallet", "Razorpay"]
        if method not in valid_methods:
            return "CASH"
        return method.upper() if method.upper() in ["CASH", "WALLET", "ONLINE"] else "CASH"

    def clean_trip_type(self):
        ttype = self.cleaned_data.get("trip_type") or "ONE_WAY"
        if ttype.upper() in ["ROUND_TRIP", "ROUNDTRIP"]:
            return "ROUND_TRIP"
        return "ONE_WAY"