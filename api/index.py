"""WSGI entry point for Vercel's Python runtime.

Vercel looks for a module-level `app` (WSGI callable) in files under
api/. Everything is routed here — see vercel.json.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

app = get_wsgi_application()
