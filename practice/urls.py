from django.urls import path

from . import views

app_name = "practice"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/round/", views.api_round, name="api_round"),
    path("api/log/", views.api_log, name="api_log"),
]
