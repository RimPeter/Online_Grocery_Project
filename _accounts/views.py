from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ConfirmPasswordForm, AddressForm
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from .utils import create_verification_code_for_user, send_verification_email
from .models import VerificationCode, Address
from django.utils.crypto import get_random_string
import logging
from smtplib import SMTPException, SMTPAuthenticationError

logger = logging.getLogger(__name__)

@login_required
def manage_addresses(request):
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            addr = form.save(commit=False)
            addr.user = request.user
            addr.save()
            # if this one should be default, unset others
            if getattr(addr, "is_default", False):
                Address.objects.filter(user=request.user).exclude(pk=addr.pk).update(is_default=False)
            messages.success(request, "Address saved.")
            return redirect("manage_addresses")
    else:
        form = AddressForm()

    addresses = request.user.addresses.all().order_by("-is_default", "city", "street_address")
    return render(request, "accounts/address.html", {"form": form, "addresses": addresses})

@login_required
def set_default_address(request, pk):
    if request.method != "POST":
        return redirect("manage_addresses")
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    addr.is_default = True
    addr.save(update_fields=["is_default"])
    messages.success(request, "Default address updated.")
    return redirect("manage_addresses")

@login_required
def delete_address(request, pk):
    addr = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        was_default = addr.is_default
        addr.delete()
        if was_default:
            # promote another address to default if any remain
            replacement = Address.objects.filter(user=request.user).first()
            if replacement:
                replacement.is_default = True
                replacement.save(update_fields=["is_default"])
        messages.success(request, "Address deleted.")
    return redirect("manage_addresses")


def login_view(request):
    """
    Renders a login form and handles the login process.
    """
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            context = {'error': 'Invalid username or password'}
            return render(request, 'accounts/login.html', context)

    # GET: Render the login form
    return render(request, 'accounts/login.html')

@login_required
def logout_view(request):
    """
    Logs out the user and redirects them to the home page.
    """
    logout(request)
    return redirect('home')


def signup_view(request):
    """
    Handles both GET (render sign-up page) and POST (create new user).
    """
    if request.method == 'POST':
        # Always initialize context at the top
        context = {}

        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        # 1. Check password match
        if password1 != password2:
            context['error'] = 'Passwords do not match'
            return render(request, 'accounts/signup.html', context)

        # 2. Retrieve the User model
        User = get_user_model()

        # 3. Check if username exists
        if User.objects.filter(username=username).exists():
            context['username_error'] = 'Username already taken'
            return render(request, 'accounts/signup.html', context)

        # 4. Check if email exists
        if User.objects.filter(email=email).exists():
            context['email_error'] = 'Email address already in use'
            return render(request, 'accounts/signup.html', context)

        # 5. Create the user
        new_user = User.objects.create(
            username=username,
            email=email,
            phone=phone,
            password=make_password(password1),
            is_active=False  # User must verify email before logging in
        )
        code = create_verification_code_for_user(new_user)
        email_ok = send_verification_email(new_user, code)

        new_user = User.objects.create(
            username=username, email=email, phone=phone,
            password=make_password(password1), is_active=False
        )
        code = create_verification_code_for_user(new_user)
        email_ok = send_verification_email(new_user, code)
        
        if not email_ok:
            if settings.DEBUG:
                messages.warning(
                    request,
                    f"We couldn't send the email (dev). Use this code: {code}"
                )
            else:
                messages.error(request,
                    "We couldn’t send your verification email right now. Please try again later.")
            return redirect('verify_account')

        messages.success(request, "Your account has been created, but we need to verify your email address. Check your inbox for the code.")
        return redirect('verify_account')

        

    # GET: Render the signup page (no context needed by default)
    return render(request, 'accounts/signup.html')

def verify_account(request):
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()

        if not code:
            return render(request, 'accounts/verify_account.html', {'error': 'Please enter a valid code.'})

        try:
            # Find the verification entry
            vc = VerificationCode.objects.get(code=code, is_used=False, user__is_active=False)
        except VerificationCode.DoesNotExist:
            # Code not found or already used
            return render(request, 'accounts/verify_account.html', {'error': 'Invalid or expired code.'})

        # If we get here, the code is correct and belongs to an inactive user
        user = vc.user
        user.is_active = True
        user.save()

        # Mark the code as used
        vc.is_used = True
        vc.save()

        messages.success(request, "Your email has been verified and your account is now active. You can log in!")
        return redirect('login')

    # GET
    return render(request, 'accounts/verify_account.html')

@login_required
def delete_account(request):
    """
    Deletes the currently logged-in user's account, but requires password confirmation.
    """
    if request.method == 'POST':
        form = ConfirmPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            request.user.delete()
            messages.success(request, "Your account has been deleted.")
            return redirect('home')  # or wherever you want to redirect
        else:
            # Form not valid (password incorrect). The form will show an error message.
            return render(request, 'accounts/delete_account.html', {'form': form})
    else:
        # GET request: Show the confirmation form
        form = ConfirmPasswordForm(user=request.user)
        return render(request, 'accounts/delete_account.html', {'form': form})
    
def send_welcome_email(request):
    # Suppose you already have the user email
    user_email = 'test.user@example.com'

    subject = "Welcome to Our Awesome App!"
    message = (
        "Hi there,\n\n"
        "Thanks for signing up. We're excited to have you on board!\n\n"
        "Best,\nThe Team"
    )
    from_email = settings.EMAIL_HOST_USER  # or "YourName <your_gmail_address@gmail.com>"
    recipient_list = [user_email]

    send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        fail_silently=False,
    )
    return render(request, 'email_sent.html')

def send_welcome_email_advanced(request):
    user_email = 'test.user@example.com'
    subject = "Welcome to Our Awesome App!"
    body = "Hi there,\n\nThanks for signing up. Enjoy our platform!\n\nBest,\nThe Team"

    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.EMAIL_HOST_USER,
        to=[user_email],
    )
    # Optionally add an attachment or do other customizations:
    # email.attach('filename.pdf', pdf_data, 'application/pdf')
    
    email.send(fail_silently=False)
    return render(request, 'email_sent.html')

def send_html_email():
    subject = "HTML Email Test"
    plain_message = "This is the fallback text if HTML can't be rendered."
    html_message = "<h1>Welcome!</h1><p>This is an <strong>HTML</strong> email.</p>"
    from_email = settings.EMAIL_HOST_USER
    to = ['test.user@example.com']

    send_mail(
        subject,
        plain_message,
        from_email,
        to,
        html_message=html_message
    )

def custom_404_view(request, exception):
    """
    Custom 404 error handler.
    """
    return render(request, '404.html', status=404)

def forgot_password_view(request):
    """
    1. Renders a form to request the user's email (GET).
    2. Processes the form (POST), finds the user, generates a new password, sets it, and emails it.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        User = get_user_model()

        try:
            # 1. Look up the user by email
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return render(request, 'accounts/forgot_password.html', {
                'error': "No user found with that email address."
            })

        # 2. Generate a new random password (length can be changed as desired)
        new_password = get_random_string(length=10)

        # 3. Set the user's password to the new random password
        user.set_password(new_password)
        user.save()

        # 4. Send an email with the username & new password
        subject = 'Your Account Credentials'
        message = (
            f"Hello {user.username},\n\n"
            f"You requested to reset your password.\n\n"
            f"Here are your new login credentials:\n"
            f"Username: {user.username}\n"
            f"Password: {new_password}\n\n"
            f"Please log in and change your password immediately."
        )
        from_email = settings.EMAIL_HOST_USER  # Make sure this is set in settings.py
        recipient_list = [email]

        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False,
        )

        # 5. Inform the user
        messages.success(request, "A new password has been sent to your email.")
        return redirect('login')

        
    return render(request, 'accounts/forgot_password.html', {
        'error': "No user found with that email address."
    })

    