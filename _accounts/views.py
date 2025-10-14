from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ConfirmPasswordForm, AddressForm, ContactForm, ProfileForm, DeleteAccountForm
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from .utils import create_verification_code_for_user, send_verification_email
from .models import VerificationCode, Address, ContactMessage
from django.utils.crypto import get_random_string
import logging
from smtplib import SMTPException, SMTPAuthenticationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta
from .models import PendingSignup

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
    if request.method == 'POST':
        context = {}
        username = (request.POST.get('username') or "").strip()
        email = (request.POST.get('email') or "").strip()
        phone = (request.POST.get('phone') or "").strip()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            context['error'] = 'Passwords do not match'
            return render(request, 'accounts/signup.html', context)

        User = get_user_model()

        # Case-insensitive checks against existing Users
        if User.objects.filter(username__iexact=username).exists():
            context['username_error'] = 'Username already taken'
            return render(request, 'accounts/signup.html', context)

        if User.objects.filter(email__iexact=email).exists():
            context['email_error'] = 'Email address already in use'
            return render(request, 'accounts/signup.html', context)

        # Clear any expired pending records for the same username/email
        for ps in PendingSignup.objects.filter(username__iexact=username):
            if ps.is_expired():
                ps.delete()
        for ps in PendingSignup.objects.filter(email__iexact=email):
            if ps.is_expired():
                ps.delete()

        # If still pending and not expired, throttle/deny
        if PendingSignup.objects.filter(username__iexact=username).exists():
            context['username_error'] = 'A verification is already pending for this username. Check your email.'
            return render(request, 'accounts/signup.html', context)
        if PendingSignup.objects.filter(email__iexact=email).exists():
            context['email_error'] = 'A verification is already pending for this email. Check your inbox.'
            return render(request, 'accounts/signup.html', context)

        code = get_random_string(length=8).lower()  # e.g., c5532027 style
        pending = PendingSignup.objects.create(
            username=username,
            email=email,
            phone=phone,
            password_hash=make_password(password1),
            code=code,
            expires_at=timezone.now() + timedelta(minutes=30),
            requester_ip=request.META.get('REMOTE_ADDR')
        )

        email_ok = send_verification_email(
            # You can overload to accept raw details instead of a user
            # or write a new helper for pending signups:
            new_user := type('Temp', (), {'email': email, 'username': username}),  # lightweight shim
            code
        )

        if not email_ok:
            pending.delete()
            messages.error(request, "We couldn’t send your verification email right now. Please try again later.")
            return render(request, 'accounts/signup.html', {})

        messages.success(request, "We sent a verification code to your email. Enter it to finish creating your account.")
        return redirect('verify_account')

    return render(request, 'accounts/signup.html')


def verify_account(request):
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip()

        if not code:
            return render(request, 'accounts/verify_account.html', {'error': 'Please enter a valid code.'})

        try:
            pending = PendingSignup.objects.get(code=code)
        except PendingSignup.DoesNotExist:
            # Backward-compatibility: keep your old VerificationCode flow if desired
            try:
                vc = VerificationCode.objects.get(code=code, is_used=False, user__is_active=False)
            except VerificationCode.DoesNotExist:
                return render(request, 'accounts/verify_account.html', {'error': 'Invalid or expired code.'})
            # Old path: activate existing user
            user = vc.user
            user.is_active = True
            user.save(update_fields=['is_active'])
            vc.is_used = True
            vc.save(update_fields=['is_used'])
            messages.success(request, "Your email has been verified. You can log in!")
            return redirect('login')

        # New pending-signup path
        if pending.is_expired():
            pending.delete()
            return render(request, 'accounts/verify_account.html', {'error': 'Code expired. Please sign up again.'})

        User = get_user_model()
        try:
            with transaction.atomic():
                # Double-check uniqueness (case-insensitive) at commit time
                if User.objects.filter(username__iexact=pending.username).exists():
                    pending.delete()
                    return render(request, 'accounts/verify_account.html', {'error': 'Username is no longer available.'})
                if User.objects.filter(email__iexact=pending.email).exists():
                    pending.delete()
                    return render(request, 'accounts/verify_account.html', {'error': 'Email is no longer available.'})

                user = User.objects.create(
                    username=pending.username,
                    email=pending.email,
                    phone=pending.phone,
                    password=pending.password_hash,
                    is_active=True
                )
                pending.delete()
        except IntegrityError:
            return render(request, 'accounts/verify_account.html', {'error': 'That username or email was just taken. Please try again.'})

        messages.success(request, "Your email has been verified and your account is now active. You can log in!")
        return redirect('login')

    return render(request, 'accounts/verify_account.html')

@login_required
def delete_account(request):
    """
    Deletes the currently logged-in user's account, but requires password confirmation.
    """
    # simple session-based rate limiting
    LIMIT = 5          # max failed attempts
    BLOCK_SECONDS = 600  # 10 minutes
    now_ts = int(timezone.now().timestamp())
    block_until = request.session.get('delete_block_until') or 0

    if request.method == 'POST':
        # If currently blocked, do not process
        if now_ts < block_until:
            remaining = block_until - now_ts
            minutes = max(1, remaining // 60)
            form = DeleteAccountForm(user=request.user, data=request.POST)
            form.add_error(None, f'Too many attempts. Try again in about {minutes} minute(s).')
            logger.warning('delete_account rate limited', extra={
                'user_id': request.user.id,
                'ip': request.META.get('REMOTE_ADDR'),
                'remaining_seconds': remaining,
            })
            return render(request, 'accounts/delete_account.html', {'form': form})

        form = DeleteAccountForm(user=request.user, data=request.POST)
        if form.is_valid():
            # success: clear counters and log the event
            for k in ('delete_attempt_count', 'delete_block_until'):
                request.session.pop(k, None)
            logger.info('account deleted', extra={
                'user_id': request.user.id,
                'email': request.user.email,
                'ip': request.META.get('REMOTE_ADDR'),
                'ts': now_ts,
            })
            request.user.delete()
            logout(request)
            return redirect('account_deleted')
        else:
            # failed attempt: increment counter and maybe block
            attempts = int(request.session.get('delete_attempt_count') or 0) + 1
            request.session['delete_attempt_count'] = attempts
            if attempts >= LIMIT:
                request.session['delete_block_until'] = now_ts + BLOCK_SECONDS
                messages.error(request, 'Too many attempts. You are temporarily blocked from deleting your account.')
            logger.warning('delete_account failed', extra={
                'user_id': request.user.id,
                'ip': request.META.get('REMOTE_ADDR'),
                'attempts': attempts,
            })
            return render(request, 'accounts/delete_account.html', {'form': form})
    else:
        # GET request: Show the confirmation form, note if blocked
        form = DeleteAccountForm(user=request.user)
        if now_ts < block_until:
            remaining = block_until - now_ts
            minutes = max(1, remaining // 60)
            form.add_error(None, f'Deletion temporarily blocked. Try again in about {minutes} minute(s).')
        return render(request, 'accounts/delete_account.html', {'form': form})


def account_deleted(request):
    """Render a static confirmation page after account deletion."""
    return render(request, 'accounts/account_deleted.html')
    
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

        
    return render(request, 'accounts/forgot_password.html')

    
@login_required
def contact_us(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            cm = form.save(commit=False)
            cm.user = request.user
            cm.save()
            # send confirmation email to the customer
            try:
                user_email = (request.user.email or '').strip()
                if user_email:
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None) or 'no-reply@example.com'
                    subject = 'We received your message'
                    lines = [
                        f'Hi {request.user.username},',
                        '',
                        'Thanks for contacting us. We have received your message and will get back to you soon.',
                        '',
                        'Summary:',
                        f'Subject: {cm.subject or "(none)"}',
                        '',
                        cm.message,
                        '',
                        'Best regards,',
                        'Customer Support'
                    ]
                    send_mail(subject, '\n'.join(lines), from_email, [user_email], fail_silently=True)
            except Exception:
                # do not block user flow on email issues
                logger.exception('contact confirmation email failed')
            messages.success(request, 'Thanks for reaching out. We will get back to you soon.')
            return redirect('contact_submitted')
    else:
        initial = {
            'subject': request.GET.get('subject', ''),
            'message': request.GET.get('message', ''),
        }
        form = ContactForm(initial=initial)
    return render(request, 'accounts/contact.html', {'form': form})


@login_required
def contact_submitted(request):
    email = (request.user.email or '').strip()
    return render(request, 'accounts/contact_submitted.html', {'email': email})


@login_required
def profile_view(request):
    profile_form = ProfileForm(request.user, instance=request.user)
    address_form = AddressForm()

    if request.method == 'POST':
        # Distinguish which form was submitted
        if request.POST.get('profile_submit') is not None:
            profile_form = ProfileForm(request.user, data=request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
        elif request.POST.get('address_submit') is not None:
            address_form = AddressForm(request.POST)
            if address_form.is_valid():
                addr = address_form.save(commit=False)
                addr.user = request.user
                addr.save()
                if getattr(addr, 'is_default', False):
                    Address.objects.filter(user=request.user).exclude(pk=addr.pk).update(is_default=False)
                messages.success(request, 'Address added.')
                return redirect('profile')

    addresses = request.user.addresses.all().order_by('-is_default', 'city', 'street_address')
    return render(request, 'accounts/profile.html', {
        'form': profile_form,
        'address_form': address_form,
        'addresses': addresses,
    })
