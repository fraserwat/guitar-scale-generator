from django.urls import path

from . import views
from .ratelimit import rate_limit

app_name = "practice"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/round/", views.api_round, name="api_round"),
    # Rate-limited at the URL layer (not in views.py) so the throttle policy
    # stays separate from the endpoint's validation logic.
    path("api/log/", rate_limit("log")(views.api_log), name="api_log"),
]
