import json
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase

from _analytics.tracking import (
    _timestamp_to_datetime,
    classify_browser_family,
    classify_device_type,
    extract_utm_data,
    infer_traffic_source,
    track_event,
)
from _analytics.views import _is_safe_internal_landing_path, _parse_days, visits_page_daily, visits_summary


class _Session(dict):
    session_key = 'session-123'


class AnalyticsHelpersTests(SimpleTestCase):
    def test_parse_days_clamps_and_falls_back(self):
        self.assertEqual(_parse_days('30'), 30)
        self.assertEqual(_parse_days('0'), 1)
        self.assertEqual(_parse_days('99999'), 3650)
        self.assertEqual(_parse_days('abc'), 30)
        self.assertEqual(_parse_days(None, default=90), 90)

    def test_safe_internal_landing_path(self):
        self.assertTrue(_is_safe_internal_landing_path('/products/fruit'))
        self.assertFalse(_is_safe_internal_landing_path('products/fruit'))
        self.assertFalse(_is_safe_internal_landing_path('//example.com'))
        self.assertFalse(_is_safe_internal_landing_path(''))

    def test_tracking_helper_classification(self):
        self.assertEqual(classify_device_type('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'), 'mobile')
        self.assertEqual(classify_device_type('Mozilla/5.0 (Windows NT 10.0; Win64; x64)'), 'desktop')
        self.assertEqual(classify_browser_family('Mozilla/5.0 Chrome/122.0 Safari/537.36'), 'Chrome')
        self.assertEqual(classify_browser_family('Mozilla/5.0 Version/17.0 Safari/605.1.15'), 'Safari')

    def test_extracts_utm_and_infers_source(self):
        utm = extract_utm_data('utm_source=newsletter&utm_medium=email&utm_campaign=spring')
        self.assertEqual(utm['utm_campaign'], 'spring')
        self.assertEqual(
            infer_traffic_source(referrer='', utm_data=utm, host='example.com'),
            'email',
        )
        self.assertEqual(
            infer_traffic_source(referrer='https://www.google.com/search?q=shop', utm_data={}, host='example.com'),
            'search',
        )


class AnalyticsTrackingTests(SimpleTestCase):
    def test_timestamp_to_datetime_returns_aware_utc_datetime(self):
        converted = _timestamp_to_datetime(1710000000)

        self.assertIsNotNone(converted)
        self.assertEqual(converted.tzinfo, dt_timezone.utc)
        self.assertEqual(int(converted.timestamp()), 1710000000)

    @patch('_analytics.tracking.get_or_create_active_visit', side_effect=DatabaseError('missing table'))
    def test_track_event_swallow_schema_errors(self, _get_visit_mock):
        request = RequestFactory().post('/cart/')
        request.session = _Session()
        request.path = '/cart/'

        self.assertIsNone(track_event(request, 'add_to_cart'))

    @patch('_analytics.tracking.AnalyticsEvent')
    @patch('_analytics.tracking.get_or_create_active_visit')
    def test_track_event_creates_event_with_normalized_value(self, get_visit_mock, event_model_mock):
        request = RequestFactory().post('/cart/')
        request.session = _Session()
        request.path = '/cart/'
        request.current_pageview = SimpleNamespace(pk=9)
        get_visit_mock.return_value = (SimpleNamespace(pk=7), False)

        track_event(
            request,
            'checkout_started',
            value='12.50',
            properties={'order_id': 44},
        )

        create_kwargs = event_model_mock.objects.create.call_args.kwargs
        self.assertEqual(create_kwargs['event_type'], 'checkout_started')
        self.assertEqual(str(create_kwargs['value']), '12.50')
        self.assertEqual(create_kwargs['properties']['order_id'], 44)
        self.assertEqual(create_kwargs['session_key'], 'session-123')


class AnalyticsViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.staff_user = SimpleNamespace(is_active=True, is_staff=True)

    def test_visits_page_daily_rejects_unsafe_paths(self):
        request = self.factory.get('/analytics/visits/page/daily/', {'path': '//example.com', 'days': '30'})
        request.user = self.staff_user

        response = visits_page_daily(request)

        self.assertEqual(response.status_code, 400)

    @patch('_analytics.views._summary_payload', return_value={'ok': True})
    @patch('_analytics.views._apply_event_filters')
    @patch('_analytics.views._apply_pageview_filters')
    @patch('_analytics.views._apply_visit_filters')
    @patch('_analytics.views.AnalyticsEvent')
    @patch('_analytics.views.VisitPageview')
    @patch('_analytics.views.Visit')
    def test_visits_summary_uses_default_days_when_invalid(
        self,
        visit_model_mock,
        pageview_model_mock,
        event_model_mock,
        apply_visit_filters_mock,
        apply_pageview_filters_mock,
        apply_event_filters_mock,
        summary_payload_mock,
    ):
        request = self.factory.get('/analytics/visits/', {'days': 'invalid'})
        request.user = self.staff_user

        apply_visit_filters_mock.return_value = MagicMock()
        apply_pageview_filters_mock.return_value = MagicMock()
        apply_event_filters_mock.return_value = MagicMock()
        visit_model_mock.objects.filter.return_value = MagicMock()
        pageview_model_mock.objects.filter.return_value = MagicMock()
        event_model_mock.objects.filter.return_value = MagicMock()

        response = visits_summary(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload, {'ok': True})
        window_arg = summary_payload_mock.call_args.args[3]
        self.assertEqual(window_arg['days'], 30)

    @patch('_analytics.views.Visit')
    def test_visits_summary_returns_503_when_schema_missing(self, visit_model_mock):
        request = self.factory.get('/analytics/visits/', {'days': '30'})
        request.user = self.staff_user
        visit_model_mock.objects.filter.side_effect = DatabaseError('missing column')

        response = visits_summary(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 503)
        self.assertIn('migrate _analytics', payload['error'])
