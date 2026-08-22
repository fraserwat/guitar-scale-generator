"""Tests for the per-IP rate limit on POST /api/log/ (practice/ratelimit.py)."""

import json
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


def _post(client, **extra):
    """POST a syntactically valid JSON body; content doesn't matter for the
    throttle (over-limit requests are rejected before validation)."""
    return client.post(
        reverse("practice:api_log"),
        data=json.dumps({}),
        content_type="application/json",
        **extra,
    )


@override_settings(API_RATE_LIMIT_PER_MINUTE=3)
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        # Freeze time so every request in a test lands in the same window —
        # otherwise a test straddling a minute boundary would flake.
        patcher = mock.patch("practice.ratelimit.time.time", return_value=1_000_000.0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_requests_within_limit_are_not_throttled(self):
        for _ in range(3):
            response = _post(self.client)
            # 400 (empty payload fails validation), never 429.
            self.assertEqual(response.status_code, 400)

    def test_request_over_limit_gets_429_with_retry_after(self):
        for _ in range(3):
            _post(self.client)
        response = _post(self.client)
        self.assertEqual(response.status_code, 429)
        self.assertIn("errors", response.json())
        retry_after = int(response["Retry-After"])
        self.assertTrue(1 <= retry_after <= 60)

    def test_limit_is_per_ip(self):
        for _ in range(3):
            _post(self.client, REMOTE_ADDR="192.0.2.1")
        self.assertEqual(
            _post(self.client, REMOTE_ADDR="192.0.2.1").status_code, 429
        )
        # A different client is unaffected.
        self.assertEqual(
            _post(self.client, REMOTE_ADDR="192.0.2.2").status_code, 400
        )

    def test_new_window_resets_the_counter(self):
        for _ in range(4):
            _post(self.client)
        self.assertEqual(_post(self.client).status_code, 429)
        with mock.patch(
            "practice.ratelimit.time.time", return_value=1_000_000.0 + 60
        ):
            self.assertEqual(_post(self.client).status_code, 400)

    @override_settings(API_RATE_LIMIT_PER_MINUTE=0)
    def test_zero_limit_disables_throttling(self):
        for _ in range(10):
            self.assertEqual(_post(self.client).status_code, 400)

    def test_round_endpoint_is_not_rate_limited(self):
        for _ in range(10):
            response = self.client.get(reverse("practice:api_round"))
            self.assertEqual(response.status_code, 200)
