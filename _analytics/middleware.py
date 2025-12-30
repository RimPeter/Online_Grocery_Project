from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Visit


@dataclass(frozen=True)
class _VisitSettings:
    session_timeout_seconds: int
    last_seen_update_seconds: int
    excluded_path_prefixes: tuple[str, ...]


def _get_visit_settings() -> _VisitSettings:
    return _VisitSettings(
        session_timeout_seconds=int(getattr(settings, 'VISIT_SESSION_TIMEOUT_SECONDS', 30 * 60)),
        last_seen_update_seconds=int(getattr(settings, 'VISIT_LAST_SEEN_UPDATE_SECONDS', 60)),
        excluded_path_prefixes=tuple(
            getattr(
                settings,
                'VISIT_EXCLUDED_PATH_PREFIXES',
                (
                    '/admin/',
                    '/static/',
                    '/media/',
                    '/favicon.ico',
                ),
            )
        ),
    )


class VisitTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._track(request, response)
        except Exception:
            pass
        return response

    def _should_track(self, request, response, visit_settings: _VisitSettings) -> bool:
        if request.method != 'GET':
            return False

        path = getattr(request, 'path', '') or ''
        if any(path.startswith(prefix) for prefix in visit_settings.excluded_path_prefixes):
            return False

        if getattr(response, 'status_code', 500) >= 400:
            return False

        content_type = (response.get('Content-Type') or '').lower()
        if 'text/html' not in content_type:
            return False

        return True

    def _track(self, request, response) -> None:
        visit_settings = _get_visit_settings()
        if not self._should_track(request, response, visit_settings):
            return

        if not hasattr(request, 'session'):
            return

        if request.session.session_key is None:
            request.session.save()

        now = timezone.now()
        now_ts = int(now.timestamp())
        timeout = timedelta(seconds=visit_settings.session_timeout_seconds)

        visit_id = request.session.get('visit_id')
        last_seen_ts = request.session.get('visit_last_seen_ts')
        last_db_update_ts = request.session.get('visit_last_db_update_ts')

        last_seen_at = None
        if isinstance(last_seen_ts, int):
            last_seen_at = timezone.datetime.fromtimestamp(last_seen_ts, tz=timezone.utc)

        is_new_visit = (
            visit_id is None
            or last_seen_at is None
            or (now - last_seen_at) > timeout
        )

        user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None

        if is_new_visit:
            visit = Visit.objects.create(
                session_key=request.session.session_key,
                user=user,
                started_at=now,
                last_seen_at=now,
                landing_path=getattr(request, 'path', '') or '',
                landing_query=getattr(request, 'META', {}).get('QUERY_STRING', '') or '',
                referrer=getattr(request, 'META', {}).get('HTTP_REFERER', '') or '',
                user_agent=getattr(request, 'META', {}).get('HTTP_USER_AGENT', '') or '',
            )
            request.session['visit_id'] = visit.pk
            request.session['visit_last_seen_ts'] = now_ts
            request.session['visit_last_db_update_ts'] = now_ts
            return

        request.session['visit_last_seen_ts'] = now_ts

        if not isinstance(last_db_update_ts, int) or (now_ts - last_db_update_ts) >= visit_settings.last_seen_update_seconds:
            Visit.objects.filter(pk=visit_id).update(last_seen_at=now, user=user)
            request.session['visit_last_db_update_ts'] = now_ts

