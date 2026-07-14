"""URL configuration for the config project.

The Django admin is intentionally not routed (and django.contrib.admin is
not in INSTALLED_APPS — see config/settings.py): no models are registered,
so its login page would be pure attack surface. Restore both when
users/auth land.
"""
from django.urls import include, path

urlpatterns = [
    path("", include("practice.urls")),
]
