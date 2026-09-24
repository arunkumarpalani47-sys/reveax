import json
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from booking.models import Booking
from .models import Payment, Wallet, WalletTransaction
from .forms import PaymentForm
from .services import (
    get_or_create_wallet,
    credit_wallet,
    debit_wallet,
    create_razorpay_order,
    process_trip_payment,
)


@login_required
def payment_list(request):
    if request.user.role == "ADMIN":
        payments = Payment.objects.all().order_by("-payment_date")
    elif request.user.role == "PARTNER":
        payments = Payment.objects.filter(
            booking__vehicle__owner=request.user
        ).order_by("-payment_date")
    else:  # CUSTOMER
        payments = Payment.objects.filter(
            booking__customer=request.user
        ).order_by("-payment_date")

    return render(request, "payment/payment_list.html", {
        "payments": payments
    })


@login_required
def make_payment(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id)
    except Exception:
        messages.error(request, "Booking not found.")
        return redirect("booking_list")

    if request.user.role == "CUSTOMER" and str(booking.customer_id) != str(request.user.id):
        messages.error(request, "You can only pay for your own bookings.")
        return redirect("booking_list")

    # If already paid
    existing_payment = Payment.objects.filter(booking=booking, payment_status="Paid").first()
    if existing_payment or booking.payment_status == "PAID":
        messages.info(request, "This booking has already been paid.")
        return redirect("booking_invoice", id=booking.id)

    wallet = get_or_create_wallet(request.user)

    if request.method == "POST":
        method = request.POST.get("payment_method", "Cash")
        success, msg = process_trip_payment(booking, method)
        if success:
            messages.success(request, msg)
            return redirect("booking_invoice", id=booking.id)
        else:
            messages.error(request, msg)

    from django.conf import settings
    form = PaymentForm()
    return render(request, "payment/payment_form.html", {
        "form": form,
        "booking": booking,
        "wallet": wallet,
        "RAZORPAY_KEY_ID": getattr(settings, "RAZORPAY_KEY_ID", "rzp_test_rovexaKey123"),
    })


@login_required
def wallet_view(request):
    """
    Customer & Driver In-App Wallet Dashboard.
    """
    import os
    wallet = get_or_create_wallet(request.user)
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by("-created_at")[:20]

    return render(request, "payment/wallet.html", {
        "wallet": wallet,
        "transactions": transactions,
        "RAZORPAY_KEY_ID": os.environ.get("RAZORPAY_KEY_ID", "rzp_test_rovexaKey123"),
    })


@login_required
def booking_invoice(request, id):
    """
    Printable & Downloadable Rovexa Ride Receipt / Invoice.
    """
    try:
        booking = Booking.objects.get(id=id)
    except Exception:
        messages.error(request, "Invoice not found.")
        return redirect("booking_list")

    # Security check: Customer, Driver assigned, Partner, or Admin can view
    user = request.user
    if user.role == "CUSTOMER" and str(booking.customer_id) != str(user.id):
        messages.error(request, "Access denied.")
        return redirect("booking_list")

    payment = Payment.objects.filter(booking=booking).first()

    return render(request, "payment/invoice.html", {
        "booking": booking,
        "payment": payment,
    })


# ── REST APIs for Wallet & Razorpay ───────────────────────────────────────────

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_topup_wallet(request):
    """
    POST /payment/api/wallet/topup/
    Body: {"amount": 500, "razorpay_payment_id": "pay_xxx"}
    """
    try:
        data = json.loads(request.body)
        amount = float(data.get("amount", 0))
        rzp_id = data.get("razorpay_payment_id", f"TOPUP_{str(request.user.id)}")

        if amount <= 0:
            return JsonResponse({"success": False, "message": "Amount must be greater than 0."}, status=400)

        txn = credit_wallet(
            user=request.user,
            amount=amount,
            description="Wallet Top-Up (Online Payment)",
            razorpay_id=rzp_id
        )

        wallet = get_or_create_wallet(request.user)
        return JsonResponse({
            "success": True,
            "message": f"Successfully added ₹{amount:.2f} to your Rovexa Wallet!",
            "new_balance": float(wallet.balance),
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_wallet_pay(request):
    """
    POST /payment/api/wallet/pay/
    Body: {"booking_id": "..."}
    """
    try:
        data = json.loads(request.body)
        booking_id = data.get("booking_id")

        booking = Booking.objects.get(id=booking_id)

        if str(booking.customer_id) != str(request.user.id):
            return JsonResponse({"success": False, "message": "Access denied."}, status=403)

        success, msg = process_trip_payment(booking, "WALLET")
        if success:
            return JsonResponse({
                "success": True,
                "message": msg,
                "invoice_url": f"/payment/invoice/{booking.id}/"
            })
        else:
            return JsonResponse({"success": False, "message": msg}, status=400)

    except Booking.DoesNotExist:
        return JsonResponse({"success": False, "message": "Booking not found."}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_razorpay_create_order(request):
    """
    POST /payment/api/razorpay/create-order/
    Body: {"amount": 250}
    """
    try:
        data = json.loads(request.body)
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return JsonResponse({"success": False, "message": "Amount must be greater than 0."}, status=400)

        order_data = create_razorpay_order(amount)
        return JsonResponse({"success": True, "order": order_data})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_bank_withdrawal(request):
    """
    POST /payment/api/wallet/withdraw/
    Body: {"amount": 500, "account_number": "1234567890", "ifsc_code": "SBIN0001234", "account_holder": "Arun Kumar", "bank_name": "State Bank of India"}
    """
    try:
        from .services import process_withdrawal_request
        data = json.loads(request.body)
        amount = float(data.get("amount", 0))
        acc_no = data.get("account_number", "").strip()
        ifsc   = data.get("ifsc_code", "").strip()
        holder = data.get("account_holder", "").strip()
        bank   = data.get("bank_name", "State Bank of India").strip()

        if amount <= 0 or not acc_no or not ifsc or not holder:
            return JsonResponse({"success": False, "message": "All bank details & valid amount are required."}, status=400)

        success, msg = process_withdrawal_request(
            user=request.user,
            amount=amount,
            account_number=acc_no,
            ifsc_code=ifsc,
            account_holder=holder,
            bank_name=bank
        )

        if success:
            wallet = get_or_create_wallet(request.user)
            return JsonResponse({"success": True, "message": msg, "new_balance": float(wallet.balance)})
        else:
            return JsonResponse({"success": False, "message": msg}, status=400)

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)

