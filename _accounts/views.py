from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import ConfirmPasswordForm
from django.core.mail import send_mail, EmailMessage
from django.conf import settings

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
            password=make_password(password1),  # Hashes the password
        )

        # 6. (Optional) Log the user in automatically
        # login(request, new_user)

        # 7. Redirect to login or home, whichever you prefer
        return redirect('login')

    # GET: Render the signup page (no context needed by default)
    return render(request, 'accounts/signup.html')

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
        [to],
        html_message=html_message
    )
