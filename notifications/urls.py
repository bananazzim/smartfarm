from django.urls import path

from .views import alert_management

urlpatterns = [path("", alert_management, name="notifications")]
