
from django import forms
from .models import Address, ContactMessage

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "street_address",
            "apartment",
            "city",
            "postal_code",
            "delivery_instructions",
            "is_default",
        ]
        widgets = {
            "street_address": forms.TextInput(attrs={"class": "form-control"}),
            "apartment": forms.TextInput(attrs={"class": "form-control"}),
            "city": forms.TextInput(attrs={"class": "form-control"}),
            "postal_code": forms.TextInput(attrs={"class": "form-control"}),
            "delivery_instructions": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

class ConfirmPasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'}),
        label='Confirm Your Password'
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user  # Keep a reference to the currently logged-in user

    def clean_password(self):
        """Validate that the provided password matches the user's actual password."""
        password = self.cleaned_data.get('password')
        if not self.user.check_password(password):
            raise forms.ValidationError('Incorrect password. Please try again.')
        return password


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['subject', 'message']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject (optional)'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Write your message...'}),
        }
