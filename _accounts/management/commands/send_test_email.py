# _accounts/management/commands/send_test_email.py
# python manage.py send_test_email --to primaszecsi@gmail.com

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMessage, get_connection
from django.conf import settings
from datetime import datetime
from zoneinfo import ZoneInfo
import os

def _env_bool(val, default=False):
    if val is None:
        return default
    return str(val).lower() in {"1", "true", "t", "yes", "y"}

class Command(BaseCommand):
    help = "Send a test email using current EMAIL_* env/settings (with optional overrides)."

    def add_arguments(self, parser):
        parser.add_argument("--to", nargs="+", default=["primaszecsi@gmail.com"], help="Recipient email(s)")
        parser.add_argument("--from", dest="from_email", default=None, help="From email (defaults to DEFAULT_FROM_EMAIL/EMAIL_HOST_USER)")
        parser.add_argument("--subject", default="SMTP test from Django", help="Email subject")
        parser.add_argument("--body", default=None, help="Email body (default includes timestamp)")
        # Optional SMTP overrides (otherwise uses env/settings)
        parser.add_argument("--host", default=None, help="SMTP host")
        parser.add_argument("--port", type=int, default=None, help="SMTP port")
        parser.add_argument("--user", default=None, help="SMTP username")
        parser.add_argument("--password", default=None, help="SMTP password (Google App Password)")
        parser.add_argument("--use-tls", action="store_true", help="Force STARTTLS on")
        parser.add_argument("--use-ssl", action="store_true", help="Force SSL on")
        parser.add_argument("--timeout", type=int, default=20, help="SMTP timeout seconds")
        parser.add_argument("--dry-run", action="store_true", help="Print config and exit")

    def handle(self, *args, **opts):
        # Resolve config from CLI → env → settings → defaults
        host = opts["host"] or os.getenv("EMAIL_HOST") or getattr(settings, "EMAIL_HOST", "smtp.gmail.com")
        port = opts["port"] or int(os.getenv("EMAIL_PORT") or getattr(settings, "EMAIL_PORT", 587))

        # TLS/SSL resolution (avoid both True)
        use_tls = opts["use_tls"] or _env_bool(os.getenv("EMAIL_USE_TLS"), getattr(settings, "EMAIL_USE_TLS", port == 587))
        use_ssl = opts["use_ssl"] or _env_bool(os.getenv("EMAIL_USE_SSL"), getattr(settings, "EMAIL_USE_SSL", port == 465))
        if use_tls and use_ssl:
            # Prefer explicit CLI choice; otherwise default to TLS on 587
            if opts["use_ssl"] and not opts["use_tls"]:
                use_tls = False
            else:
                use_ssl = False

        user = opts["user"] or os.getenv("EMAIL_HOST_USER") or getattr(settings, "EMAIL_HOST_USER", None)
        pwd = opts["password"] or os.getenv("EMAIL_HOST_PASSWORD") or getattr(settings, "EMAIL_HOST_PASSWORD", None)

        from_email = (
            opts["from_email"]
            or os.getenv("DEFAULT_FROM_EMAIL")
            or getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or user
        )

        if not user:
            raise CommandError("Missing EMAIL_HOST_USER (SMTP username). Set it in .env or pass --user.")
        if not pwd:
            raise CommandError("Missing EMAIL_HOST_PASSWORD (SMTP password). For Gmail, this must be a 16-letter App Password.")
        if not from_email:
            raise CommandError("Could not determine FROM address. Set DEFAULT_FROM_EMAIL or pass --from.")

        # Build body
        if opts["body"]:
            body = opts["body"]
        else:
            ts = datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M:%S %Z")
            body = f"Hello! Test email sent at {ts}."

        # Diagnostics (don’t print the actual password)
        pwd_len = len(pwd)
        looks_like_app_pw = (pwd_len == 16 and pwd.isalpha())
        self.stdout.write(self.style.NOTICE(f"From: {from_email}"))
        self.stdout.write(self.style.NOTICE(f"To:   {', '.join(opts['to'])}"))
        self.stdout.write(self.style.NOTICE(f"Host: {host}  Port: {port}  SSL: {use_ssl}  TLS: {use_tls}  Timeout: {opts['timeout']}"))
        self.stdout.write(self.style.NOTICE(f"User: {user}  Password length: {pwd_len}  AppPW-ish: {looks_like_app_pw}"))

        if opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Dry-run complete."))
            return

        # Send using an explicit connection so overrides always apply
        try:
            conn = get_connection(
                backend=getattr(settings, "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"),
                host=host,
                port=port,
                username=user,
                password=pwd,
                use_tls=use_tls,
                use_ssl=use_ssl,
                timeout=opts["timeout"],
            )
            msg = EmailMessage(
                subject=opts["subject"],
                body=body,
                from_email=from_email,
                to=opts["to"],
                connection=conn,
            )
            sent = msg.send(fail_silently=False)
        except Exception as e:
            # Add quick hint for common Gmail errors
            hint = ""
            es = str(e)
            if "5.7.9" in es or "Application-specific password required" in es:
                hint = "  (Hint: You must use a Google App Password and have 2-Step Verification enabled.)"
            if "Username and Password not accepted" in es or "5.7.8" in es:
                hint = "  (Hint: Wrong username/password; use the app password for the same account as EMAIL_HOST_USER.)"
            raise CommandError(f"Send failed: {e}{hint}") from e

        self.stdout.write(self.style.SUCCESS(f"Success. Messages sent: {sent}"))
