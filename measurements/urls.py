from django.urls import path

from . import views

urlpatterns = [
    path("", views.analysis, name="analysis"),
    path("upload/", views.csv_upload, name="measurement-upload"),
]
