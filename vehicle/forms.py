from django import forms
from .models import Vehicle

class VehicleForm(forms.ModelForm):

    class Meta:
        model = Vehicle
        exclude = ["owner"]

        widgets = {
            "vehicle_name": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. Rovexa Sedan"}),
            "brand": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. Maruti Suzuki"}),
            "model": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. Swift Dzire"}),
            "vehicle_number": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. TN-01-AX-4040"}),
            "vehicle_type": forms.Select(attrs={"class":"form-select form-control-custom"}),
            "fuel_type": forms.Select(attrs={"class":"form-select form-control-custom"}),
            "seats": forms.NumberInput(attrs={"class":"form-control form-control-custom", "placeholder": "4", "min": 1}),
            "price_per_km": forms.NumberInput(attrs={"class":"form-control form-control-custom", "placeholder": "16.00", "step": "0.50"}),
            "image": forms.FileInput(attrs={"class":"form-control form-control-custom", "accept": "image/*", "id": "vehicle_image_input"}),
            "image_url": forms.URLInput(attrs={"class":"form-control form-control-custom", "placeholder": "https://images.unsplash.com/photo-..."}),
            "driver_name": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. Ramesh Kumar"}),
            "driver_phone": forms.TextInput(attrs={"class":"form-control form-control-custom", "placeholder": "e.g. +91 98452 98351"}),
            "driver_image": forms.FileInput(attrs={"class":"form-control form-control-custom", "accept": "image/*", "id": "driver_image_input"}),
            "driver_image_url": forms.URLInput(attrs={"class":"form-control form-control-custom", "placeholder": "https://images.unsplash.com/photo-..."}),
            "driver_rating": forms.NumberInput(attrs={"class":"form-control form-control-custom", "placeholder": "4.9", "step": "0.1", "min": "1.0", "max": "5.0"}),
            "is_available": forms.CheckboxInput(attrs={"class":"form-check-input", "role": "switch", "style": "width: 2.8em; height: 1.4em; cursor: pointer;"}),
        }