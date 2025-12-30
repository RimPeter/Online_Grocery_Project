from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
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
def visits_dashboard(request):
    days = int(request.GET.get('days', '30'))
    days = max(1, min(days, 3650))
    return render(
        request,
        '_analytics/visits_dashboard.html',
        {
            'default_days': days,
            'visits_summary_url': reverse('visits_summary'),
        },
    )
