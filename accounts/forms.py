import re
from django import forms
from django.core.exceptions import ValidationError
from .models import CustomUser

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control finput", "placeholder": "First Name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control finput", "placeholder": "Last Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control finput", "placeholder": "Email Address"}),
            "phone": forms.TextInput(attrs={"class": "form-control finput", "placeholder": "Phone Number"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if phone:
            # Validate 10-digit Indian phone number starting with 6-9
            clean_digits = re.sub(r"\D", "", phone)
            if len(clean_digits) == 12 and clean_digits.startswith("91"):
                clean_digits = clean_digits[2:]
            if not re.match(r"^[6-9]\d{9}$", clean_digits):
                raise ValidationError("Please enter a valid 10-digit mobile number (e.g. 9876543210).")
            return clean_digits
        return phone

    def clean_first_name(self):
        name = self.cleaned_data.get("first_name", "").strip()
        if name and not re.match(r"^[A-Za-z\s\.'-]+$", name):
            raise ValidationError("First name can only contain letters, spaces, and hyphens.")
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get("last_name", "").strip()
        if name and not re.match(r"^[A-Za-z\s\.'-]+$", name):
            raise ValidationError("Last name can only contain letters, spaces, and hyphens.")
        return name
