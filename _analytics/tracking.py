from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

from .models import AnalyticsEvent, Visit, VisitPageview


TRACKED_UTM_KEYS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content')
SOCIAL_HOST_HINTS = (
    'facebook',
    'instagram',
    'tiktok',
    'twitter',
    'x.com',
    'linkedin',
    'youtube',
    'pinterest',
)
SEARCH_HOST_HINTS = ('google', 'bing', 'yahoo', 'duckduckgo', 'ecosia')
EMAIL_HINTS = ('mail', 'newsletter', 'email')


@dataclass(frozen=True)
class VisitSettings:
    session_timeout_seconds: int
    last_seen_update_seconds: int
    excluded_path_prefixes: tuple[str, ...]


def get_visit_settings() -> VisitSettings:
    return VisitSettings(
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


def classify_device_type(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if not ua:
        return 'other'
    if any(token in ua for token in ('bot', 'spider', 'crawl', 'slurp')):
        return 'bot'
    if 'ipad' in ua or 'tablet' in ua:
        return 'tablet'
    if any(token in ua for token in ('iphone', 'android', 'mobile')):
        return 'mobile'
    if any(token in ua for token in ('windows', 'macintosh', 'linux', 'x11')):
        return 'desktop'
    return 'other'


def classify_browser_family(user_agent: str) -> str:
    ua = (user_agent or '').lower()
    if 'edg/' in ua:
        return 'Edge'
    if 'opr/' in ua or 'opera' in ua:
        return 'Opera'
    if 'chrome/' in ua and 'chromium' not in ua:
        return 'Chrome'
    if 'firefox/' in ua:
        return 'Firefox'
    if 'safari/' in ua and 'chrome/' not in ua:
        return 'Safari'
    if 'trident/' in ua or 'msie ' in ua:
        return 'Internet Explorer'
    if not ua:
        return 'Unknown'
    return 'Other'


def extract_utm_data(query_string: str) -> dict[str, str]:
    parsed = parse_qs(query_string or '', keep_blank_values=False)
    data = {}
    for key in TRACKED_UTM_KEYS:
        values = parsed.get(key, [])
        data[key] = (values[0] if values else '').strip()
    return data


def extract_referrer_host(referrer: str) -> str:
    value = (referrer or '').strip()
    if not value:
        return ''
    try:
        return (urlparse(value).hostname or '').lower()
    except ValueError:
        return ''


def infer_traffic_source(*, referrer: str, utm_data: dict[str, str], host: str) -> str:
    utm_source = (utm_data.get('utm_source') or '').lower()
    utm_medium = (utm_data.get('utm_medium') or '').lower()
    referrer_host = extract_referrer_host(referrer)
    host = (host or '').lower()

    if utm_medium in ('email', 'newsletter') or utm_source in EMAIL_HINTS:
        return 'email'
    if utm_source or utm_medium or (utm_data.get('utm_campaign') or '').strip():
        return 'campaign'
    if not referrer_host:
        return 'direct'
    if host and referrer_host == host:
        return 'direct'
    if any(hint in referrer_host for hint in SEARCH_HOST_HINTS):
        return 'search'
    if any(hint in referrer_host for hint in SOCIAL_HOST_HINTS):
        return 'social'
    return 'referral'


def should_track_request(request, response, visit_settings: VisitSettings | None = None) -> bool:
    visit_settings = visit_settings or get_visit_settings()
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


def _get_or_create_session_key(request) -> str | None:
    if not hasattr(request, 'session'):
        return None
    if request.session.session_key is None:
        request.session.save()
    return request.session.session_key


def _get_user(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return user
    return None


def _timestamp_to_datetime(value):
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=dt_timezone.utc)


def get_or_create_active_visit(request, *, now=None, create=True):
    if not hasattr(request, 'session'):
        return None, True

    visit_settings = get_visit_settings()
    session_key = _get_or_create_session_key(request)
    if not session_key:
        return None, True

    now = now or timezone.now()
    timeout = timedelta(seconds=visit_settings.session_timeout_seconds)
    now_ts = int(now.timestamp())
    visit_id = request.session.get('visit_id')
    last_seen_at = _timestamp_to_datetime(request.session.get('visit_last_seen_ts'))

    is_new_visit = (
        visit_id is None
        or last_seen_at is None
        or (now - last_seen_at) > timeout
    )

    user = _get_user(request)
    host = request.get_host().split(':', 1)[0].lower() if hasattr(request, 'get_host') else ''
    utm_data = extract_utm_data(getattr(request, 'META', {}).get('QUERY_STRING', '') or '')
    visit_defaults = {
        'session_key': session_key,
        'user': user,
        'started_at': now,
        'last_seen_at': now,
        'landing_path': getattr(request, 'path', '') or '',
        'landing_query': getattr(request, 'META', {}).get('QUERY_STRING', '') or '',
        'referrer': getattr(request, 'META', {}).get('HTTP_REFERER', '') or '',
        'referrer_host': extract_referrer_host(getattr(request, 'META', {}).get('HTTP_REFERER', '') or ''),
        'user_agent': getattr(request, 'META', {}).get('HTTP_USER_AGENT', '') or '',
        'traffic_source': infer_traffic_source(
            referrer=getattr(request, 'META', {}).get('HTTP_REFERER', '') or '',
            utm_data=utm_data,
            host=host,
        ),
        'device_type': classify_device_type(getattr(request, 'META', {}).get('HTTP_USER_AGENT', '') or ''),
        'browser_family': classify_browser_family(getattr(request, 'META', {}).get('HTTP_USER_AGENT', '') or ''),
        'is_authenticated': bool(user),
        'utm_source': utm_data['utm_source'],
        'utm_medium': utm_data['utm_medium'],
        'utm_campaign': utm_data['utm_campaign'],
        'utm_term': utm_data['utm_term'],
        'utm_content': utm_data['utm_content'],
    }

    if is_new_visit:
        if not create:
            return None, True
        visit = Visit.objects.create(**visit_defaults)
        request.session['visit_id'] = visit.pk
        request.session['visit_last_seen_ts'] = now_ts
        request.session['visit_last_db_update_ts'] = now_ts
        request.session['visit_last_pageview_id'] = None
        request.session['visit_last_pageview_ts'] = None
        request.session['visit_pageview_sequence'] = 0
        request.current_visit = visit
        return visit, True

    visit = getattr(request, 'current_visit', None)
    if visit is None or getattr(visit, 'pk', None) != visit_id:
        visit = Visit.objects.filter(pk=visit_id).first()
        if visit is None:
            if not create:
                return None, True
            visit = Visit.objects.create(**visit_defaults)
            request.session['visit_id'] = visit.pk
            request.session['visit_last_seen_ts'] = now_ts
            request.session['visit_last_db_update_ts'] = now_ts
            request.session['visit_last_pageview_id'] = None
            request.session['visit_last_pageview_ts'] = None
            request.session['visit_pageview_sequence'] = 0
            request.current_visit = visit
            return visit, True

    request.session['visit_last_seen_ts'] = now_ts
    last_db_update_ts = request.session.get('visit_last_db_update_ts')
    if (
        not isinstance(last_db_update_ts, int)
        or (now_ts - last_db_update_ts) >= visit_settings.last_seen_update_seconds
    ):
        updates = {'last_seen_at': now}
        if visit.user_id != getattr(user, 'id', None):
            updates['user'] = user
        if visit.is_authenticated != bool(user):
            updates['is_authenticated'] = bool(user)
        if updates:
            Visit.objects.filter(pk=visit.pk).update(**updates)
            for field_name, field_value in updates.items():
                setattr(visit, field_name, field_value)
        request.session['visit_last_db_update_ts'] = now_ts

    request.current_visit = visit
    return visit, False


def _update_previous_pageview_duration(request, now):
    previous_pageview_id = request.session.get('visit_last_pageview_id')
    previous_ts = _timestamp_to_datetime(request.session.get('visit_last_pageview_ts'))
    if not previous_pageview_id or previous_ts is None:
        return

    duration = max(0, int((now - previous_ts).total_seconds()))
    VisitPageview.objects.filter(pk=previous_pageview_id, duration_seconds__isnull=True).update(
        duration_seconds=duration
    )


def track_pageview(request, *, visit=None, now=None):
    now = now or timezone.now()
    visit = visit or getattr(request, 'current_visit', None)
    if visit is None:
        visit, _ = get_or_create_active_visit(request, now=now, create=True)
    if visit is None:
        return None

    _update_previous_pageview_duration(request, now)
    sequence_index = int(request.session.get('visit_pageview_sequence') or 0) + 1
    pageview = VisitPageview.objects.create(
        visit=visit,
        user=_get_user(request),
        session_key=request.session.session_key or '',
        path=getattr(request, 'path', '') or '',
        query=getattr(request, 'META', {}).get('QUERY_STRING', '') or '',
        referrer=getattr(request, 'META', {}).get('HTTP_REFERER', '') or '',
        viewed_at=now,
        sequence_index=sequence_index,
        is_authenticated=bool(_get_user(request)),
    )
    request.session['visit_last_pageview_id'] = pageview.pk
    request.session['visit_last_pageview_ts'] = int(now.timestamp())
    request.session['visit_pageview_sequence'] = sequence_index
    request.current_pageview = pageview
    return pageview


def track_request(request, response):
    try:
        if not should_track_request(request, response):
            return
        visit, _ = get_or_create_active_visit(request, create=True)
        if visit is None:
            return
        track_pageview(request, visit=visit)
    except DatabaseError:
        return


def _normalize_event_value(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def track_event(request, event_type: str, *, label: str = '', value=None, properties=None, path: str | None = None):
    try:
        if not hasattr(request, 'session'):
            return None

        now = timezone.now()
        visit, _ = get_or_create_active_visit(request, now=now, create=True)
        if visit is None:
            return None

        pageview = getattr(request, 'current_pageview', None)
        if pageview is None:
            pageview_id = request.session.get('visit_last_pageview_id')
            if pageview_id:
                pageview = VisitPageview.objects.filter(pk=pageview_id).first()

        event = AnalyticsEvent.objects.create(
            visit=visit,
            pageview=pageview,
            user=_get_user(request),
            session_key=request.session.session_key or '',
            event_type=(event_type or '').strip(),
            path=(path or getattr(request, 'path', '') or '').strip(),
            label=(label or '').strip(),
            value=_normalize_event_value(value),
            properties=properties or {},
        )
        return event
    except DatabaseError:
        return None
