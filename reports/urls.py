from django.urls import path

from .views import installation_guide

urlpatterns = [path("", installation_guide, name="report")]
