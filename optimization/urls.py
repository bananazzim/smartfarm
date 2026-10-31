from django.urls import path

from .views import optimization_results

urlpatterns = [path("", optimization_results, name="optimization")]
