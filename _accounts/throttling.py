"""Database-backed login limits shared across sessions and worker processes."""
import hashlib
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import LoginThrottle


@transaction.atomic
def allow_login_attempt(username, ip):
    now = timezone.now()
    keys = [(hashlib.sha256(f'user:{username.strip().casefold()}'.encode()).hexdigest(), 5),
            (hashlib.sha256(f'ip:{ip}'.encode()).hexdigest(), 30)]
    allowed = True
    for key, limit in sorted(keys):
        row, _ = LoginThrottle.objects.get_or_create(key=key)
        row = LoginThrottle.objects.select_for_update().get(pk=row.pk)
        if now - row.window_started >= timedelta(minutes=10):
            row.attempts = 0
            row.window_started = now
        allowed = allowed and row.attempts < limit
        row.attempts = min(row.attempts + 1, limit)
        row.save(update_fields=['attempts', 'window_started'])
    return allowed


def clear_user_login_attempts(username):
    key = hashlib.sha256(f'user:{username.strip().casefold()}'.encode()).hexdigest()
    LoginThrottle.objects.filter(key=key).update(attempts=0)
