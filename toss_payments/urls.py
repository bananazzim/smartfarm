from django.urls import path

from . import views

app_name = "toss_payments"

urlpatterns = [
    path("", views.checkout_start, name="checkout_start"),
    path("orders/", views.create_order, name="create_order"),
    path("order/<str:order_number>/", views.checkout_order, name="checkout_order"),
    path(
        "order/<str:order_number>/reservation/",
        views.save_reservation,
        name="save_reservation",
    ),
    path("success/", views.payment_success, name="payment_success"),
    path("fail/", views.payment_fail, name="payment_fail"),
]
