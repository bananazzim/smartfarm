from django.urls import path
from . import views

urlpatterns = [
    path("", views.simulator, name="simulator"),
    path("data/", views.simulator_data, name="simulator-data"),
]
