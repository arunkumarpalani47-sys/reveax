from decimal import Decimal
from django.test import TestCase
from accounts.models import CustomUser
from payment.models import Wallet, WalletTransaction
from payment.services import credit_wallet, debit_wallet

class WalletLedgerTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="wallet_user",
            password="Password123!",
            role="CUSTOMER"
        )
        self.wallet, _ = Wallet.objects.get_or_create(user=self.user)

    def test_credit_wallet(self):
        """Test crediting user wallet updates balance and creates transaction record."""
        txn = credit_wallet(
            user=self.user,
            amount=Decimal("500.00"),
            description="Test top-up",
            category="TOPUP",
            booking_ref="TXN_TEST_101"
        )
        self.assertIsNotNone(txn)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("500.00"))
        self.assertEqual(txn.amount, Decimal("500.00"))

    def test_debit_wallet_sufficient_funds(self):
        """Test debiting wallet when funds are available."""
        credit_wallet(self.user, Decimal("1000.00"), "Init credit", "TOPUP", "TXN_INIT")
        success, msg, txn = debit_wallet(
            user=self.user,
            amount=Decimal("300.00"),
            description="Ride payment",
            category="RIDE_PAYMENT",
            booking_ref="RIDE_101"
        )
        self.assertTrue(success)
        self.assertIsNotNone(txn)
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("700.00"))

    def test_debit_wallet_insufficient_funds(self):
        """Test debiting wallet fails when balance is insufficient."""
        success, msg, txn = debit_wallet(
            user=self.user,
            amount=Decimal("500.00"),
            description="Ride payment test",
            category="RIDE_PAYMENT",
            booking_ref="RIDE_102"
        )
        self.assertFalse(success)
        self.assertIsNone(txn)
        self.assertIn("Insufficient", msg)
