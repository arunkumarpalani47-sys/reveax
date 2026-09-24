from django.urls import path
from . import views

urlpatterns = [
    path("", views.payment_list, name="payment_list"),
    path("add/<str:booking_id>/", views.make_payment, name="make_payment"),
    path("wallet/", views.wallet_view, name="wallet_view"),
    path("invoice/<str:id>/", views.booking_invoice, name="booking_invoice"),

    # Sprint 5 Payment APIs
    path("api/wallet/topup/", views.api_topup_wallet, name="api_topup_wallet"),
    path("api/wallet/pay/", views.api_wallet_pay, name="api_wallet_pay"),
    path("api/wallet/withdraw/", views.api_bank_withdrawal, name="api_bank_withdrawal"),
    path("api/razorpay/create-order/", views.api_razorpay_create_order, name="api_razorpay_create_order"),
]