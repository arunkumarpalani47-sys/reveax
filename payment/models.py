from django.db import models
from accounts.models import CustomUser
from booking.models import Booking


class Wallet(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    currency = models.CharField(max_length=10, default="INR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Wallet (₹{self.balance})"


class WalletTransaction(models.Model):
    TXN_TYPES = (
        ("CREDIT", "Credit (+)"),
        ("DEBIT",  "Debit (-)"),
    )

    CATEGORIES = (
        ("TOPUP", "Wallet Top-Up"),
        ("RIDE_PAYMENT", "Ride Booking Payment"),
        ("DRIVER_EARNINGS", "Driver Trip Earnings"),
        ("WITHDRAWAL", "Bank Account Withdrawal"),
        ("REFUND", "Trip Refund"),
    )

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    closing_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00
    )
    txn_type = models.CharField(
        max_length=10,
        choices=TXN_TYPES
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORIES,
        default="TOPUP"
    )
    description = models.CharField(max_length=255)
    booking_ref = models.CharField(max_length=100, blank=True, default="")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default="")
    txn_reference_id = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.txn_type}] ₹{self.amount} (Closing: ₹{self.closing_balance}) - {self.description}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending Approval"),
        ("PROCESSED", "Processed to Bank"),
        ("REJECTED", "Rejected"),
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="withdrawals"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    account_number = models.CharField(max_length=30)
    ifsc_code = models.CharField(max_length=20)
    account_holder = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100, blank=True, default="State Bank of India")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal ₹{self.amount} for {self.user.username} [{self.status}]"


class Payment(models.Model):

    PAYMENT_METHOD = (
        ("Cash", "Cash"),
        ("UPI", "UPI"),
        ("Card", "Card"),
        ("Wallet", "Wallet"),
        ("Razorpay", "Razorpay"),
    )

    PAYMENT_STATUS = (
        ("Pending", "Pending"),
        ("Paid", "Paid"),
        ("Failed", "Failed"),
        ("Refunded", "Refunded"),
    )

    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="payment_record"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD,
        default="Cash"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default="Pending"
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    razorpay_order_id = models.CharField(max_length=100, blank=True, default="")
    razorpay_signature = models.CharField(max_length=255, blank=True, default="")

    payment_date = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Payment #{self.id} - {self.payment_status} (₹{self.amount})"