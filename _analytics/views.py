from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models import Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import Visit


@staff_member_required
def visits_summary(request):
    days = int(request.GET.get('days', '30'))
    days = max(1, min(days, 3650))

    since = timezone.now() - timedelta(days=days)
    today = timezone.localdate()

    qs = Visit.objects.filter(started_at__gte=since)
    per_day = (
        qs.annotate(day=TruncDate('started_at'))
        .values('day')
        .annotate(visits=Count('id'))
        .order_by('day')
    )

    return JsonResponse(
        {
            'days': days,
            'since': since.isoformat(),
            'total_visits': qs.count(),
            'today_visits': Visit.objects.filter(started_at__date=today).count(),
            'per_day': list(per_day),
        }
    )


@staff_member_required
def visits_pages_summary(request):
    today = timezone.localdate()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)

    pages = (
        Visit.objects.exclude(landing_path='')
        .values('landing_path')
        .annotate(
            total_visits=Count('id'),
            last_week_visits=Count(
                'id',
                filter=Q(started_at__date__gte=last_week_start, started_at__date__lte=last_week_end),
            ),
            this_week_visits=Count('id', filter=Q(started_at__date__gte=this_week_start)),
            today_visits=Count('id', filter=Q(started_at__date=today)),
        )
        .order_by('-total_visits', 'landing_path')
    )

    return JsonResponse(
        {
            'today': str(today),
            'this_week_start': str(this_week_start),
            'last_week_start': str(last_week_start),
            'last_week_end': str(last_week_end),
            'pages': list(pages),
        }
    )


@staff_member_required
def visits_dashboard(request):
    days = int(request.GET.get('days', '30'))
    days = max(1, min(days, 3650))
    return render(
        request,
        '_analytics/visits_dashboard.html',
        {
            'default_days': days,
            'visits_summary_url': reverse('visits_summary'),
            'visits_pages_summary_url': reverse('visits_pages_summary'),
        },
    )
