from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import EmptyPage, Paginator
from django.db import DatabaseError
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import AnalyticsAnnotation, AnalyticsEvent, AnalyticsSavedView, GoogleAdsLandingArrival, Visit, VisitPageview


ANALYTICS_SCHEMA_ERROR = 'Analytics database changes are not applied yet. Run manage.py migrate _analytics and reload this page.'


def _parse_days(raw_value, default=30):
    try:
        days = int(raw_value)
    except (TypeError, ValueError):
        days = default
    return max(1, min(days, 3650))


def _parse_bool(raw_value) -> bool:
    return str(raw_value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _parse_iso_date(raw_value):
    value = str(raw_value or '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _format_date(value):
    return value.isoformat() if value else ''


def _date_bounds(start_date, end_date):
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), tz)
    return start_dt, end_dt


def _resolve_window(request, default_days=30):
    days = _parse_days(request.GET.get('days'), default=default_days)
    today = timezone.localdate()
    start_date = _parse_iso_date(request.GET.get('start'))
    end_date = _parse_iso_date(request.GET.get('end'))

    if start_date and end_date and start_date <= end_date:
        resolved_start = start_date
        resolved_end = end_date
        resolved_days = (end_date - start_date).days + 1
    else:
        resolved_end = today
        resolved_start = today - timedelta(days=days - 1)
        resolved_days = days

    start_dt, end_dt = _date_bounds(resolved_start, resolved_end)
    previous_start_dt = start_dt - (end_dt - start_dt)
    previous_end_dt = start_dt
    return {
        'days': resolved_days,
        'start_date': resolved_start,
        'end_date': resolved_end,
        'start_dt': start_dt,
        'end_dt': end_dt,
        'compare_enabled': _parse_bool(request.GET.get('compare')),
        'previous_start_dt': previous_start_dt,
        'previous_end_dt': previous_end_dt,
    }


def _is_safe_internal_landing_path(path):
    value = (path or '').strip()
    return value.startswith('/') and not value.startswith('//')


def _build_filters(request):
    return {
        'device': (request.GET.get('device') or '').strip(),
        'browser': (request.GET.get('browser') or '').strip(),
        'user_scope': (request.GET.get('user_scope') or 'all').strip() or 'all',
        'source': (request.GET.get('source') or '').strip(),
        'campaign': (request.GET.get('campaign') or '').strip(),
    }


def _apply_visit_filters(qs, filters):
    if filters['device']:
        qs = qs.filter(device_type=filters['device'])
    if filters['browser']:
        qs = qs.filter(browser_family=filters['browser'])
    if filters['source']:
        qs = qs.filter(traffic_source=filters['source'])
    if filters['campaign']:
        qs = qs.filter(utm_campaign=filters['campaign'])
    if filters['user_scope'] == 'authenticated':
        qs = qs.filter(is_authenticated=True)
    elif filters['user_scope'] == 'anonymous':
        qs = qs.filter(is_authenticated=False)
    return qs


def _apply_pageview_filters(qs, filters):
    if filters['device']:
        qs = qs.filter(visit__device_type=filters['device'])
    if filters['browser']:
        qs = qs.filter(visit__browser_family=filters['browser'])
    if filters['source']:
        qs = qs.filter(visit__traffic_source=filters['source'])
    if filters['campaign']:
        qs = qs.filter(visit__utm_campaign=filters['campaign'])
    if filters['user_scope'] == 'authenticated':
        qs = qs.filter(visit__is_authenticated=True)
    elif filters['user_scope'] == 'anonymous':
        qs = qs.filter(visit__is_authenticated=False)
    return qs


def _apply_event_filters(qs, filters):
    if filters['device']:
        qs = qs.filter(visit__device_type=filters['device'])
    if filters['browser']:
        qs = qs.filter(visit__browser_family=filters['browser'])
    if filters['source']:
        qs = qs.filter(visit__traffic_source=filters['source'])
    if filters['campaign']:
        qs = qs.filter(visit__utm_campaign=filters['campaign'])
    if filters['user_scope'] == 'authenticated':
        qs = qs.filter(visit__is_authenticated=True)
    elif filters['user_scope'] == 'anonymous':
        qs = qs.filter(visit__is_authenticated=False)
    return qs


def _apply_google_ads_arrival_filters(qs, filters):
    qs = qs.filter(Q(user__isnull=True) | Q(user__is_superuser=False))
    if filters['device']:
        qs = qs.filter(device_type=filters['device'])
    if filters['browser']:
        qs = qs.filter(browser_family=filters['browser'])
    if filters['source']:
        qs = qs.filter(traffic_source=filters['source'])
    if filters['campaign']:
        qs = qs.filter(utm_campaign=filters['campaign'])
    if filters['user_scope'] == 'authenticated':
        qs = qs.filter(is_authenticated=True)
    elif filters['user_scope'] == 'anonymous':
        qs = qs.filter(is_authenticated=False)
    return qs


def _comparison_payload(current, previous):
    if previous in (None, 0):
        delta_pct = None if current == 0 else 100.0
    else:
        delta_pct = round(((current - previous) / previous) * 100, 1)
    return {
        'current': current,
        'previous': previous,
        'delta_pct': delta_pct,
    }


def _unique_visitor_count(visits_qs):
    return len({(user_id or 0, session_key or '') for user_id, session_key in visits_qs.values_list('user_id', 'session_key')})


def _average_session_seconds(visits_qs):
    total_seconds = 0
    count = 0
    for started_at, last_seen_at in visits_qs.values_list('started_at', 'last_seen_at'):
        if not started_at or not last_seen_at:
            continue
        total_seconds += max(0, int((last_seen_at - started_at).total_seconds()))
        count += 1
    return round(total_seconds / count, 1) if count else 0


def _average_page_dwell_seconds(pageviews_qs):
    avg = pageviews_qs.exclude(duration_seconds__isnull=True).aggregate(avg=Avg('duration_seconds')).get('avg')
    return round(float(avg), 1) if avg is not None else 0


def _bounce_rate(visits_qs, start_dt, end_dt):
    total_sessions = visits_qs.count()
    if total_sessions == 0:
        return 0
    bounced = (
        visits_qs.annotate(
            pageview_count=Count(
                'pageviews',
                filter=Q(pageviews__viewed_at__gte=start_dt, pageviews__viewed_at__lt=end_dt),
                distinct=True,
            )
        )
        .filter(pageview_count__lte=1)
        .count()
    )
    return round((bounced / total_sessions) * 100, 1)


def _serialize_breakdown(qs, field_name, *, limit=8, label_key='label', count_key='count', exclude_blank=True):
    if exclude_blank:
        qs = qs.exclude(**{field_name: ''})
    rows = (
        qs.values(field_name)
        .annotate(count=Count('id'))
        .order_by('-count', field_name)[:limit]
    )
    payload = []
    for row in rows:
        payload.append(
            {
                label_key: row[field_name] or 'Unknown',
                count_key: row['count'],
            }
        )
    return payload


def _build_time_series(visits_qs, pageviews_qs):
    sessions_by_day = {
        row['day']: row['sessions']
        for row in (
            visits_qs.annotate(day=TruncDate('started_at'))
            .values('day')
            .annotate(sessions=Count('id'))
            .order_by('day')
        )
    }
    pageviews_by_day = {
        row['day']: row['pageviews']
        for row in (
            pageviews_qs.annotate(day=TruncDate('viewed_at'))
            .values('day')
            .annotate(pageviews=Count('id'))
            .order_by('day')
        )
    }
    days = sorted(set(sessions_by_day) | set(pageviews_by_day))
    return [
        {
            'day': day.isoformat(),
            'sessions': sessions_by_day.get(day, 0),
            'pageviews': pageviews_by_day.get(day, 0),
        }
        for day in days
    ]


def _build_google_ads_arrivals_series(arrivals_qs):
    return [
        {
            'day': row['day'].isoformat(),
            'arrivals': row['arrivals'],
        }
        for row in (
            arrivals_qs.annotate(day=TruncDate('arrived_at'))
            .values('day')
            .annotate(arrivals=Count('id'))
            .order_by('day')
        )
    ]


def _conversion_totals(events_qs):
    tracked_events = ['signup_started', 'signup_completed', 'add_to_cart', 'checkout_started', 'paid_order', 'order_item_paid']
    rows = (
        events_qs.filter(event_type__in=tracked_events)
        .values('event_type')
        .annotate(count=Count('id'))
    )
    data = {name: 0 for name in tracked_events}
    for row in rows:
        data[row['event_type']] = row['count']
    return data


def _build_funnel(visits_qs, pageviews_qs, events_qs):
    sessions = visits_qs.count()
    product_page_sessions = pageviews_qs.filter(path__startswith='/product/').values('session_key').distinct().count()
    add_to_cart_sessions = events_qs.filter(event_type='add_to_cart').values('session_key').distinct().count()
    checkout_sessions = events_qs.filter(event_type='checkout_started').values('session_key').distinct().count()
    paid_sessions = events_qs.filter(event_type='paid_order').values('session_key').distinct().count()

    steps = [
        ('sessions', 'Sessions', sessions),
        ('product_views', 'Product page visits', product_page_sessions),
        ('add_to_cart', 'Add to cart', add_to_cart_sessions),
        ('checkout_started', 'Checkout started', checkout_sessions),
        ('paid_orders', 'Paid orders', paid_sessions),
    ]
    payload = []
    previous = None
    for key, label, count in steps:
        rate = None if previous in (None, 0) else round((count / previous) * 100, 1)
        payload.append({'key': key, 'label': label, 'count': count, 'rate_from_previous': rate})
        previous = count
    return payload


def _decimal_from_value(value):
    if value in (None, ''):
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _build_product_performance(events_qs, *, limit=10):
    product_rows = {}
    category_rows = {}
    for event_type, label, properties in events_qs.filter(event_type__in=['add_to_cart', 'order_item_paid']).values_list(
        'event_type',
        'label',
        'properties',
    ):
        props = properties or {}
        product_id = str(props.get('product_id') or '')
        product_label = label or props.get('product_name') or f'Product {product_id}'
        category_label = props.get('sub_category') or props.get('main_category') or 'Uncategorized'
        quantity = int(_decimal_from_value(props.get('quantity') or 0 or 0))
        revenue = _decimal_from_value(props.get('line_total'))

        product_row = product_rows.setdefault(
            product_id or product_label,
            {
                'product_id': product_id,
                'label': product_label,
                'add_to_cart': 0,
                'paid_quantity': 0,
                'paid_revenue': Decimal('0'),
            },
        )
        category_row = category_rows.setdefault(
            category_label,
            {
                'label': category_label,
                'add_to_cart': 0,
                'paid_quantity': 0,
                'paid_revenue': Decimal('0'),
            },
        )

        if event_type == 'add_to_cart':
            add_qty = quantity or 1
            product_row['add_to_cart'] += add_qty
            category_row['add_to_cart'] += add_qty
        else:
            paid_qty = quantity or 1
            product_row['paid_quantity'] += paid_qty
            product_row['paid_revenue'] += revenue
            category_row['paid_quantity'] += paid_qty
            category_row['paid_revenue'] += revenue

    product_payload = sorted(
        product_rows.values(),
        key=lambda row: (row['paid_revenue'], row['paid_quantity'], row['add_to_cart']),
        reverse=True,
    )[:limit]
    category_payload = sorted(
        category_rows.values(),
        key=lambda row: (row['paid_revenue'], row['paid_quantity'], row['add_to_cart']),
        reverse=True,
    )[:limit]
    for row in product_payload:
        row['paid_revenue'] = str(row['paid_revenue'].quantize(Decimal('0.01')))
    for row in category_payload:
        row['paid_revenue'] = str(row['paid_revenue'].quantize(Decimal('0.01')))
    return product_payload, category_payload


def _summary_payload(visits_qs, pageviews_qs, events_qs, google_ads_arrivals_qs, window, filters):
    sessions = visits_qs.count()
    unique_visitors = _unique_visitor_count(visits_qs)
    pageviews = pageviews_qs.count()
    avg_session_seconds = _average_session_seconds(visits_qs)
    avg_page_dwell_seconds = _average_page_dwell_seconds(pageviews_qs)
    bounce_rate = _bounce_rate(visits_qs, window['start_dt'], window['end_dt'])
    google_ads_arrivals = google_ads_arrivals_qs.count()
    active_users = _apply_visit_filters(
        Visit.objects.filter(last_seen_at__gte=timezone.now() - timedelta(minutes=5)),
        filters,
    ).count()

    comparison = {}
    if window['compare_enabled']:
        previous_visits = _apply_visit_filters(
            Visit.objects.filter(started_at__gte=window['previous_start_dt'], started_at__lt=window['previous_end_dt']),
            filters,
        )
        previous_pageviews = _apply_pageview_filters(
            VisitPageview.objects.filter(viewed_at__gte=window['previous_start_dt'], viewed_at__lt=window['previous_end_dt']),
            filters,
        )
        comparison = {
            'sessions': _comparison_payload(sessions, previous_visits.count()),
            'unique_visitors': _comparison_payload(unique_visitors, _unique_visitor_count(previous_visits)),
            'pageviews': _comparison_payload(pageviews, previous_pageviews.count()),
            'google_ads_arrivals': _comparison_payload(
                google_ads_arrivals,
                _apply_google_ads_arrival_filters(
                    GoogleAdsLandingArrival.objects.filter(
                        arrived_at__gte=window['previous_start_dt'],
                        arrived_at__lt=window['previous_end_dt'],
                    ),
                    filters,
                ).count(),
            ),
            'paid_orders': _comparison_payload(
                events_qs.filter(event_type='paid_order').count(),
                _apply_event_filters(
                    AnalyticsEvent.objects.filter(
                        created_at__gte=window['previous_start_dt'],
                        created_at__lt=window['previous_end_dt'],
                        event_type='paid_order',
                    ),
                    filters,
                ).count(),
            ),
        }

    campaigns = []
    campaign_rows = (
        visits_qs.exclude(utm_campaign='')
        .values('utm_campaign')
        .annotate(
            sessions=Count('id'),
            paid_orders=Count('events', filter=Q(events__event_type='paid_order'), distinct=True),
        )
        .order_by('-sessions', 'utm_campaign')[:8]
    )
    for row in campaign_rows:
        campaigns.append(
            {
                'label': row['utm_campaign'],
                'sessions': row['sessions'],
                'paid_orders': row['paid_orders'],
            }
        )

    product_performance, category_performance = _build_product_performance(events_qs)
    annotations = [
        {
            'date': row.event_date.isoformat(),
            'title': row.title,
            'note': row.note,
            'color': row.color,
        }
        for row in AnalyticsAnnotation.objects.filter(
            event_date__gte=window['start_date'],
            event_date__lte=window['end_date'],
        )[:12]
    ]

    return {
        'window': {
            'start': _format_date(window['start_date']),
            'end': _format_date(window['end_date']),
            'days': window['days'],
            'compare': window['compare_enabled'],
        },
        'filters': filters,
        'available_filters': {
            'devices': list(Visit.objects.exclude(device_type='').values_list('device_type', flat=True).distinct().order_by('device_type')),
            'browsers': list(Visit.objects.exclude(browser_family='').values_list('browser_family', flat=True).distinct().order_by('browser_family')),
            'sources': list(Visit.objects.exclude(traffic_source='').values_list('traffic_source', flat=True).distinct().order_by('traffic_source')),
            'campaigns': list(Visit.objects.exclude(utm_campaign='').values_list('utm_campaign', flat=True).distinct().order_by('utm_campaign')[:50]),
        },
        'totals': {
            'sessions': sessions,
            'today_sessions': visits_qs.filter(started_at__date=timezone.localdate()).count(),
            'unique_visitors': unique_visitors,
            'pageviews': pageviews,
            'google_ads_arrivals': google_ads_arrivals,
            'avg_session_seconds': avg_session_seconds,
            'avg_page_dwell_seconds': avg_page_dwell_seconds,
            'bounce_rate': bounce_rate,
            'active_users': active_users,
        },
        'comparison': comparison,
        'per_day': _build_time_series(visits_qs, pageviews_qs),
        'google_ads_arrivals_per_day': _build_google_ads_arrivals_series(google_ads_arrivals_qs),
        'source_breakdown': _serialize_breakdown(visits_qs, 'traffic_source'),
        'device_breakdown': _serialize_breakdown(visits_qs, 'device_type'),
        'browser_breakdown': _serialize_breakdown(visits_qs, 'browser_family'),
        'top_referrers': _serialize_breakdown(visits_qs, 'referrer_host', limit=10),
        'campaigns': campaigns,
        'conversion_totals': _conversion_totals(events_qs),
        'funnel': _build_funnel(visits_qs, pageviews_qs, events_qs),
        'product_performance': product_performance,
        'category_performance': category_performance,
        'annotations': annotations,
    }


@staff_member_required
def visits_summary(request):
    try:
        window = _resolve_window(request, default_days=30)
        filters = _build_filters(request)

        visits_qs = _apply_visit_filters(
            Visit.objects.filter(started_at__gte=window['start_dt'], started_at__lt=window['end_dt']),
            filters,
        )
        pageviews_qs = _apply_pageview_filters(
            VisitPageview.objects.filter(viewed_at__gte=window['start_dt'], viewed_at__lt=window['end_dt']),
            filters,
        )
        events_qs = _apply_event_filters(
            AnalyticsEvent.objects.filter(created_at__gte=window['start_dt'], created_at__lt=window['end_dt']),
            filters,
        )
        google_ads_arrivals_qs = _apply_google_ads_arrival_filters(
            GoogleAdsLandingArrival.objects.filter(
                arrived_at__gte=window['start_dt'],
                arrived_at__lt=window['end_dt'],
            ),
            filters,
        )
        return JsonResponse(_summary_payload(visits_qs, pageviews_qs, events_qs, google_ads_arrivals_qs, window, filters))
    except DatabaseError:
        return JsonResponse({'error': ANALYTICS_SCHEMA_ERROR}, status=503)


@staff_member_required
def visits_page_daily(request):
    path = (request.GET.get('path') or '').strip()
    if not _is_safe_internal_landing_path(path):
        return JsonResponse({'error': 'Invalid path'}, status=400)
    try:
        window = _resolve_window(request, default_days=30)
        filters = _build_filters(request)
        pageviews_qs = _apply_pageview_filters(
            VisitPageview.objects.filter(
                viewed_at__gte=window['start_dt'],
                viewed_at__lt=window['end_dt'],
                path=path,
            ),
            filters,
        )
        visits_qs = _apply_visit_filters(
            Visit.objects.filter(
                started_at__gte=window['start_dt'],
                started_at__lt=window['end_dt'],
                pageviews__path=path,
            ).distinct(),
            filters,
        )

        per_day = _build_time_series(visits_qs, pageviews_qs)
        next_page_counts = defaultdict(int)
        visit_ids = list(pageviews_qs.values_list('visit_id', flat=True).distinct())
        for visit_id in visit_ids:
            sequence = list(
                pageviews_qs.model.objects.filter(visit_id=visit_id, viewed_at__gte=window['start_dt'], viewed_at__lt=window['end_dt'])
                .order_by('sequence_index', 'viewed_at')
                .values_list('path', flat=True)
            )
            for index, current_path in enumerate(sequence[:-1]):
                if current_path == path:
                    next_page = sequence[index + 1]
                    next_page_counts[next_page] += 1

        next_pages = [
            {'label': page, 'count': count}
            for page, count in sorted(next_page_counts.items(), key=lambda row: (-row[1], row[0]))[:10]
        ]
        top_referrers = _serialize_breakdown(pageviews_qs.exclude(referrer=''), 'referrer', limit=8, exclude_blank=False)

        return JsonResponse(
            {
                'path': path,
                'window': {
                    'start': _format_date(window['start_date']),
                    'end': _format_date(window['end_date']),
                    'days': window['days'],
                },
                'total_sessions': visits_qs.count(),
                'total_pageviews': pageviews_qs.count(),
                'avg_dwell_seconds': _average_page_dwell_seconds(pageviews_qs),
                'per_day': per_day,
                'next_pages': next_pages,
                'top_referrers': top_referrers,
            }
        )
    except DatabaseError:
        return JsonResponse({'error': ANALYTICS_SCHEMA_ERROR}, status=503)


@staff_member_required
def visits_pages_summary(request):
    try:
        window = _resolve_window(request, default_days=30)
        filters = _build_filters(request)
        search = (request.GET.get('q') or '').strip()
        sort = (request.GET.get('sort') or 'pageviews').strip()
        page_number = _parse_days(request.GET.get('page'), default=1)
        per_page = min(100, _parse_days(request.GET.get('per_page'), default=12))

        pageviews_qs = _apply_pageview_filters(
            VisitPageview.objects.filter(viewed_at__gte=window['start_dt'], viewed_at__lt=window['end_dt']),
            filters,
        )
        if search:
            pageviews_qs = pageviews_qs.filter(path__icontains=search)

        rows = list(
            pageviews_qs.values('path')
            .annotate(
                pageviews=Count('id'),
                sessions=Count('visit', distinct=True),
                avg_dwell_seconds=Avg('duration_seconds'),
            )
        )
        for row in rows:
            row['path'] = row['path'] or ''
            row['avg_dwell_seconds'] = round(float(row['avg_dwell_seconds'] or 0), 1)

        reverse_sort = sort != 'path'
        sort_key_map = {
            'path': lambda row: row['path'],
            'sessions': lambda row: row['sessions'],
            'avg_dwell': lambda row: row['avg_dwell_seconds'],
            'pageviews': lambda row: row['pageviews'],
        }
        rows.sort(key=sort_key_map.get(sort, sort_key_map['pageviews']), reverse=reverse_sort)

        paginator = Paginator(rows, per_page)
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages or 1)

        return JsonResponse(
            {
                'window': {
                    'start': _format_date(window['start_date']),
                    'end': _format_date(window['end_date']),
                    'days': window['days'],
                },
                'search': search,
                'sort': sort,
                'page': page_obj.number,
                'pages': paginator.num_pages,
                'total_rows': paginator.count,
                'results': list(page_obj.object_list),
            }
        )
    except DatabaseError:
        return JsonResponse({'error': ANALYTICS_SCHEMA_ERROR}, status=503)


@staff_member_required
def visits_dashboard(request):
    analytics_boot_error = ''
    try:
        saved_views = [
            {
                'name': view.name,
                'config': view.config,
                'is_default': view.is_default,
            }
            for view in AnalyticsSavedView.objects.filter(user=request.user)
        ]
    except DatabaseError:
        saved_views = []
        analytics_boot_error = ANALYTICS_SCHEMA_ERROR
    return render(
        request,
        '_analytics/visits_dashboard.html',
        {
            'default_days': _resolve_window(request, default_days=30)['days'],
            'visits_summary_url': reverse('visits_summary'),
            'visits_pages_summary_url': reverse('visits_pages_summary'),
            'visits_page_daily_url': reverse('visits_page_daily'),
            'saved_views': saved_views,
            'analytics_boot_error': analytics_boot_error,
        },
    )
