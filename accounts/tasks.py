# accounts/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_otp_email(gmail: str, code: str):
    """
    Send OTP email asynchronously.
    """
    subject = "Your password reset OTP"
    message = f"Your OTP code is: {code}\nThis code will expire in {getattr(settings, 'PASSWORD_RESET_OTP_EXPIRY_MINUTES', 10)} minutes."
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    # send_mail will use console backend in dev (so it prints)
    send_mail(subject, message, from_email, [gmail], fail_silently=False)
    return True
