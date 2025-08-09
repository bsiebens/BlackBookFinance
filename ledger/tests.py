from decimal import Decimal

from django.test import TestCase

from commodities.models import Commodity
from ledger.models import Account, Bank


class AccountModelTestCase(TestCase):

    def setUp(self):
        self.bank = Bank.objects.create(name="Test Bank")
        self.currency = Commodity.objects.create(name="Dollar", code="USD", commodity_type=Commodity.CommodityTypes.CURRENCY)
        self.account = Account.objects.create(name="Main Account", type=Account.AccountTypes.ASSETS, bank=self.bank, default_currency=self.currency)

    def test_balance_no_transactions(self):
        balance = self.account.balance

        self.assertEqual(balance.amount, Decimal(0))
        self.assertEqual(str(balance.currency), self.account.default_currency.code)

    def test_balance_with_transactions_same_currency(self):
        raise NotImplementedError

    def test_balance_with_transactions_different_currency(self):
        raise NotImplementedError

    # def test_account_creation(self):
    #     self.assertEqual(Account.objects.count(), 1)
    #     account = Account.objects.first()
    #     self.assertEqual(account.name, "Main Account")
    #     self.assertEqual(account.type, Account.AccountTypes.ASSETS)
    #     self.assertEqual(account.bank, self.bank)
    #     self.assertEqual(account.default_currency, self.currency)
    #
    # def test_account_string_representation(self):
    #     self.assertEqual(str(self.account), f"Assets:{self.account.name}")
    #
    # def test_balance_property(self):
    #     balance = self.account.balance
    #     self.assertEqual(balance.amount, 0)
    #     self.assertEqual(balance.currency.code, self.currency.code)
    #
    # def test_account_unique_name_per_parent_constraint(self):
    #     another_account = Account(
    #         name="Main Account",
    #         type=Account.AccountTypes.LIABILITIES,
    #         default_currency=self.currency,
    #     )
    #     with self.assertRaises(ValidationError):
    #         another_account.full_clean()
    #
    # def test_default_currency_limit_choices(self):
    #     invalid_currency = Commodity.objects.create(name="Stock Commodity", code="AAPL", commodity_type=Commodity.CommodityTypes.STOCK)
    #     account = Account(name="Invalid Currency Account", type=Account.AccountTypes.OTHER, default_currency=invalid_currency)
    #     with self.assertRaises(ValidationError):
    #         account.full_clean()
