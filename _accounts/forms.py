
from django import forms
from .models import Address, ContactMessage, User

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


class DeleteAccountForm(ConfirmPasswordForm):
    confirm = forms.CharField(
        label='Type DELETE to confirm',
        help_text='This is permanent. Orders are retained, login will be disabled.',
        widget=forms.TextInput(attrs={'placeholder': 'DELETE', 'class': 'form-control'})
    )

    def clean_confirm(self):
        val = (self.cleaned_data.get('confirm') or '').strip()
        if val != 'DELETE':
            raise forms.ValidationError('You must type DELETE to proceed')
        return val


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['subject', 'message']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject (optional)'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Write your message...'}),
        }


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'first_name', 'last_name']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_user = user

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if User.objects.filter(username__iexact=username).exclude(pk=self._current_user.pk).exists():
            raise forms.ValidationError('Username already taken')
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self._current_user.pk).exists():
            raise forms.ValidationError('Email address already in use')
        return email
