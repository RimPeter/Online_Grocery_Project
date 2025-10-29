
from django import forms
from .models import Address, ContactMessage, User, Company
from django.utils.text import slugify

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


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'legal_name', 'slug',
            'email', 'support_email', 'phone', 'website',
            'company_number', 'vat_number', 'tax_id',
            'address_line1', 'address_line2', 'city', 'region', 'postal_code', 'country',
            'logo',
            'currency_code', 'timezone', 'invoice_prefix', 'invoice_footer',
            'notes', 'is_default',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'legal_name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'support_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'company_number': forms.TextInput(attrs={'class': 'form-control'}),
            'vat_number': forms.TextInput(attrs={'class': 'form-control'}),
            'tax_id': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'currency_code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 3}),
            'timezone': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'invoice_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip()
        name = (self.cleaned_data.get('name') or '').strip()
        if not slug and name:
            slug = slugify(name)[:150]
        return slug
