from django.contrib import admin
from django.urls import include, path
from measurements.views import ingest_measurements

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/measurements/ingest/", ingest_measurements, name="measurement-ingest"),
    path("", include("greenhouses.urls")),
    path("analysis/", include("measurements.urls")),
    path("optimization/", include("optimization.urls")),
    path("simulator/", include("visualization.urls")),
    path("notifications/", include("notifications.urls")),
    path("reports/", include("reports.urls")),
    path("payments/", include("toss_payments.urls")),
]

handler400 = "config.views.bad_request"
handler403 = "config.views.permission_denied"
handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"
