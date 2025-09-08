import uuid
import logging
from smtplib import SMTPException, SMTPAuthenticationError
from django.core.mail import send_mail
from django.conf import settings
from .models import VerificationCode
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__) # Configure logger for this module

def create_verification_code_for_user(user):
    """Generate a unique code and store it in the VerificationCode model."""
    code = str(uuid.uuid4())[:8]  # short random code, e.g., "a1b2-c3d4"
    vc, _ = VerificationCode.objects.get_or_create(user=user)
    vc.code = code
    vc.is_used = False
    vc.save()
    return code

def send_verification_email(user, code) -> bool:
    """Send the verification code to the user's email."""
    subject = "Your Verification Code"
    message = f"Hello {user.username},\n\nHere is your verification code: {code}\n\n"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    try:
        send_mail(
            subject,
            message,
            from_email,
            recipient_list,
            fail_silently=False
        )
        logger.info("Sent verification email from %s to %s", from_email, user.email)
        return sent > 0
    except (SMTPAuthenticationError, SMTPException, Exception) as e:
        logger.exception("Verification email failed for %s: %s", user.username, e)
        return False