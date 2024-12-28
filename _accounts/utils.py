import uuid
from django.core.mail import send_mail
from django.conf import settings
from .models import VerificationCode

def create_verification_code_for_user(user):
    """Generate a unique code and store it in the VerificationCode model."""
    code = str(uuid.uuid4())[:8]  # short random code, e.g., "a1b2-c3d4"
    vc, created = VerificationCode.objects.get_or_create(user=user)
    vc.code = code
    vc.is_used = False
    vc.save()
    return code

def send_verification_email(user, code):
    """Send the verification code to the user's email."""
    subject = "Your Verification Code"
    message = f"Hello {user.username},\n\nHere is your verification code: {code}\n\n"
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [user.email]

    send_mail(
        subject,
        message,
        from_email,
        recipient_list,
        fail_silently=False
    )
