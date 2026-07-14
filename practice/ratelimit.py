"""Minimal per-IP rate limiting for API endpoints (SECURITY_AUDIT.md M1).

Fixed-window counter backed by Django's cache framework. With the default
LocMemCache the counters are per-process — adequate for the current
single-process deployment; point CACHES at Redis/Memcached if the app ever
runs multiple workers, or the effective limit multiplies by worker count.

Clients are keyed by REMOTE_ADDR. Behind a reverse proxy every client shares
the proxy's address, so the limit becomes global: terminate with a real IP
(or a trusted, proxy-stripped X-Forwarded-For scheme) before tightening it.

No Django imports happen at module import time beyond the cache/settings
facades, and the limit is read per-request so tests can use
@override_settings(API_RATE_LIMIT_PER_MINUTE=...).
"""

import functools
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

WINDOW_SECONDS = 60
# Cache entries outlive the window slightly so a request that straddles the
# boundary still finds its counter; stale windows simply expire.
CACHE_TIMEOUT = WINDOW_SECONDS * 2


def rate_limit(scope):
    """Decorate a view with a per-IP, per-minute request cap.

    The cap comes from settings.API_RATE_LIMIT_PER_MINUTE at request time;
    zero or negative disables limiting. Over-limit requests get JSON 429
    with a Retry-After header.
    """

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            limit = getattr(settings, "API_RATE_LIMIT_PER_MINUTE", 0)
            if limit <= 0:
                return view(request, *args, **kwargs)

            ip = request.META.get("REMOTE_ADDR", "unknown")
            window = int(time.time() // WINDOW_SECONDS)
            key = f"ratelimit:{scope}:{ip}:{window}"

            # add() is atomic: exactly one request creates the counter.
            if cache.add(key, 1, timeout=CACHE_TIMEOUT):
                count = 1
            else:
                try:
                    count = cache.incr(key)
                except ValueError:  # counter expired between add() and incr()
                    cache.add(key, 1, timeout=CACHE_TIMEOUT)
                    count = 1

            if count > limit:
                retry_after = WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS
                response = JsonResponse(
                    {"error": "Rate limit exceeded. Try again shortly."},
                    status=429,
                )
                response["Retry-After"] = str(retry_after)
                return response

            return view(request, *args, **kwargs)

        return wrapper

    return decorator
