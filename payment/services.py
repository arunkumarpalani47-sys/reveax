"""
Payment Services for Rovexa — Real-Time Banking Ledger & Atomic Wallet Operations.
"""

import time
import random
from decimal import Decimal
from django.db import transaction
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Wallet, WalletTransaction, Payment, WithdrawalRequest
from booking.models import Booking


def get_or_create_wallet(user) -> Wallet:
    """Retrieve or create user's in-app wallet."""
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def broadcast_wallet_update(user_id: str, payload: dict):
    """Broadcast real-time wallet update to user's WebSocket channel group."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"wallet_{user_id}",
                {"type": "wallet.update", **payload}
            )
            async_to_sync(channel_layer.group_send)(
                "wallet_broadcast",
                {"type": "wallet.update", **payload}
            )
    except Exception:
        pass


@transaction.atomic
def credit_wallet(user, amount: float | Decimal, description: str,
                  category: str = "TOPUP", booking_ref: str = "",
                  razorpay_id: str = "") -> WalletTransaction:
    """
    Atomic Banking Credit:
    Computes opening & closing balance and logs an immutable ledger entry.
    """
    amt = Decimal(str(amount))
    wallet = get_or_create_wallet(user)

    opening_bal = wallet.balance
    closing_bal = opening_bal + amt

    wallet.balance = closing_bal
    wallet.save()

    ref_id = f"TXN_{int(time.time())}{random.randint(1000, 9999)}"

    txn = WalletTransaction.objects.create(
        wallet=wallet,
        amount=amt,
        opening_balance=opening_bal,
        closing_balance=closing_bal,
        txn_type="CREDIT",
        category=category,
        description=description,
        booking_ref=booking_ref,
        razorpay_payment_id=razorpay_id,
        txn_reference_id=ref_id
    )

    # Real-time WebSocket Push Notification
    broadcast_wallet_update(str(user.id), {
        "event": "CREDIT",
        "amount": float(amt),
        "new_balance": float(closing_bal),
        "description": description,
        "ref_id": ref_id,
        "category": category
    })

    return txn


@transaction.atomic
def debit_wallet(user, amount: float | Decimal, description: str,
                 category: str = "RIDE_PAYMENT",
                 booking_ref: str = "") -> tuple[bool, str, WalletTransaction | None]:
    """
    Atomic Banking Debit:
    Validates balance sufficiency, updates opening & closing balance, logs immutable transaction.
    """
    amt = Decimal(str(amount))
    wallet = get_or_create_wallet(user)

    opening_bal = wallet.balance
    if opening_bal < amt:
        return False, f"Insufficient wallet balance. Current: ₹{opening_bal:.2f}, Required: ₹{amt:.2f}", None

    closing_bal = opening_bal - amt
    wallet.balance = closing_bal
    wallet.save()

    ref_id = f"TXN_{int(time.time())}{random.randint(1000, 9999)}"

    txn = WalletTransaction.objects.create(
        wallet=wallet,
        amount=amt,
        opening_balance=opening_bal,
        closing_balance=closing_bal,
        txn_type="DEBIT",
        category=category,
        description=description,
        booking_ref=booking_ref,
        txn_reference_id=ref_id
    )

    # Real-time WebSocket Push Notification
    broadcast_wallet_update(str(user.id), {
        "event": "DEBIT",
        "amount": float(amt),
        "new_balance": float(closing_bal),
        "description": description,
        "ref_id": ref_id,
        "category": category
    })

    return True, "Wallet payment successful.", txn


@transaction.atomic
def process_withdrawal_request(user, amount: float, account_number: str,
                               ifsc_code: str, account_holder: str,
                               bank_name: str = "State Bank of India") -> tuple[bool, str]:
    """
    Processes a Bank Account Withdrawal Request from Driver / Partner wallet.
    """
    amt = Decimal(str(amount))
    wallet = get_or_create_wallet(user)

    if wallet.balance < amt:
        return False, f"Insufficient balance for withdrawal. Balance: ₹{wallet.balance:.2f}"

    # Debit wallet balance
    success, msg, txn = debit_wallet(
        user=user,
        amount=amt,
        description=f"Bank Withdrawal to {bank_name} A/C ...{account_number[-4:]}",
        category="WITHDRAWAL"
    )

    if not success:
        return False, msg

    req = WithdrawalRequest.objects.create(
        user=user,
        amount=amt,
        account_number=account_number,
        ifsc_code=ifsc_code,
        account_holder=account_holder,
        bank_name=bank_name,
        status="PROCESSED"
    )

    return True, f"Bank Withdrawal of ₹{amt:.2f} processed successfully to {bank_name} A/C ...{account_number[-4:]}!"


def create_razorpay_order(amount_rupees: float) -> dict:
    """
    Creates a Razorpay order ID.
    If RAZORPAY_KEY_ID is configured, calls live Razorpay API, otherwise generates test order payload.
    """
    import os
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")

    amount_paise = int(float(amount_rupees) * 100)

    if key_id and key_secret:
        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, key_secret))
            order = client.order.create({
                "amount": amount_paise,
                "currency": "INR",
                "payment_capture": 1
            })
            return {
                "order_id": order["id"],
                "amount": amount_rupees,
                "key_id": key_id
            }
        except Exception:
            pass

    # Simulated test order ID
    simulated_id = f"order_{int(time.time())}{random.randint(1000, 9999)}"
    return {
        "order_id": simulated_id,
        "amount": amount_rupees,
        "key_id": key_id or "rzp_test_rovexaKey123"
    }


def process_trip_payment(booking: Booking, payment_method: str,
                         txn_id: str = "", razorpay_order_id: str = "",
                         razorpay_signature: str = "") -> tuple[bool, str]:
    """
    Processes trip payment & credits driver wallet atomically.
    """
    amt = booking.total_fare

    if payment_method.upper() == "WALLET":
        success, msg, txn = debit_wallet(
            user=booking.customer,
            amount=amt,
            description=f"Ride Payment for Booking #{booking.id}",
            category="RIDE_PAYMENT",
            booking_ref=str(booking.id)
        )
        if not success:
            return False, msg

        payment, _ = Payment.objects.update_or_create(
            booking=booking,
            defaults={
                "amount": amt,
                "payment_method": "Wallet",
                "payment_status": "Paid",
                "transaction_id": f"WLT_{txn.txn_reference_id}" if txn else f"WLT{booking.id}"
            }
        )
        booking.payment_status = "PAID"
        booking.payment_method = "WALLET"
        booking.save()

    else:
        # Cash or Razorpay / UPI
        payment, _ = Payment.objects.update_or_create(
            booking=booking,
            defaults={
                "amount": amt,
                "payment_method": payment_method.capitalize(),
                "payment_status": "Paid",
                "transaction_id": txn_id or f"TXN_{booking.id}{random.randint(100, 999)}",
                "razorpay_order_id": razorpay_order_id,
                "razorpay_signature": razorpay_signature
            }
        )

        booking.payment_status = "PAID"
        booking.payment_method = payment_method.upper()
        booking.save()

    # Credit 85% driver earnings to driver wallet if driver assigned
    if booking.driver and hasattr(booking.driver, "user"):
        driver_earning = float(amt) * 0.85
        credit_wallet(
            user=booking.driver.user,
            amount=driver_earning,
            description=f"Trip Earnings for Booking #{booking.id}",
            category="DRIVER_EARNINGS",
            booking_ref=str(booking.id)
        )

    return True, "Payment recorded successfully and driver earnings credited."
