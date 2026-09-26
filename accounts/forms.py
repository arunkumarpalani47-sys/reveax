import re
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import CustomUser


class UserProfileForm(forms.ModelForm):
    phone = forms.CharField(
        required=True,
        error_messages={
            "required": "Mobile number is mandatory.",
        },
        widget=forms.TextInput(attrs={
            "class": "form-control finput",
            "placeholder": "10-digit Indian Mobile Number (e.g. 9876543210)",
            "maxlength": "14"
        })
    )

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "phone"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control finput", "placeholder": "First Name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control finput", "placeholder": "Last Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control finput", "placeholder": "Email Address"}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()
        if not phone:
            raise ValidationError("Mobile number is mandatory.")

        if re.search(r"[a-zA-Z]", phone):
            raise ValidationError("Mobile number cannot contain letters. Please enter digits only.")

        clean_digits = re.sub(r"\D", "", phone)
        if len(clean_digits) == 12 and clean_digits.startswith("91"):
            clean_digits = clean_digits[2:]
        elif len(clean_digits) == 11 and clean_digits.startswith("0"):
            clean_digits = clean_digits[1:]

        if len(clean_digits) != 10:
            raise ValidationError("Please enter a valid 10-digit Indian mobile number (e.g. 9876543210).")

        if not re.match(r"^[6-9]\d{9}$", clean_digits):
            raise ValidationError("Invalid Indian mobile number. Mobile numbers must start with 6, 7, 8, or 9 (e.g. 9876543210).")

        # Uniqueness check excluding current instance
        existing = CustomUser.objects.filter(
            Q(phone=clean_digits) | Q(phone=f"+91{clean_digits}") | Q(phone=f"91{clean_digits}") | Q(phone__endswith=clean_digits)
        )
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError("This mobile number is already registered to another account.")

        return clean_digits

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
