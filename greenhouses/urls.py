from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("greenhouses/", views.greenhouse_list, name="greenhouse-list"),
    path("greenhouses/add/", views.greenhouse_create, name="greenhouse-create"),
    path("greenhouses/<int:pk>/", views.greenhouse_detail, name="greenhouse-detail"),
    path("greenhouses/<int:pk>/edit/", views.greenhouse_update, name="greenhouse-update"),
]
