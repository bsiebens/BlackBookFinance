from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode

from commodities.models import Commodity


def _get_base_currency():
    base_currency = getattr(settings, "BASE_CURRENCY", ("Euro", "EUR"))

    return Commodity.objects.get_or_create(code=base_currency[1], name=base_currency[0], commodity_type=Commodity.CommodityTypes.CURRENCY)[0].id


class Bank(models.Model):
    """
    Represents a bank entity used in financial or organizational contexts.

    This class defines the structure and behavior of a bank, allowing it to be uniquely identified by its name.
    It supports Django's ORM functionality by inheriting from the `models.Model` class and includes localization support for internationalized applications.

    :ivar name: The unique name of the bank.
    :type name: Str
    """

    name = models.CharField(_("name"), max_length=250, unique=True, db_index=True)

    class Meta:
        verbose_name = _("bank")
        verbose_name_plural = _("banks")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Account(TreeNode):
    """
    Represents an account in a hierarchical structure within a financial or operational context.

    The `Account` class allows for the organization of entities such as assets, liabilities, and other financial categories, providing support for default currencies and related banks.

    :ivar name: The name of the account.
    :type name: Str
    :ivar type: The type of the account, chosen from predefined account types.
    :type type: Str
    :ivar bank: The bank associated with the account, allowing null values.
    :type bank: Bank
    :ivar default_currency: The default currency of the account, restricted to commodities of type "currency".
    :type default_currency: Commodity
    :ivar created: The timestamp when the account was created.
    :type created: datetime.datetime
    :ivar updated: The timestamp when the account was last updated.
    :type updated: datetime.datetime
    """

    class AccountTypes(models.TextChoices):
        ASSETS = "assets", _("Assets")
        LIABILITIES = "liabilities", _("Liabilities")
        EXPENSES = "expenses", _("Expenses")
        INCOME = "income", _("Income")
        EQUITY = "equity", _("Equity")
        CASH = "cash", _("Cash")
        OTHER = "other", _("Other")

    name = models.CharField(_("name"), max_length=250, db_index=True)
    type = models.CharField(_("type"), max_length=15, choices=AccountTypes.choices, default=AccountTypes.OTHER)
    bank = models.ForeignKey(Bank, verbose_name=_("bank"), on_delete=models.SET_NULL, blank=True, null=True, related_name="accounts")
    default_currency = models.ForeignKey(
        Commodity,
        limit_choices_to={"commodity_type": Commodity.CommodityTypes.CURRENCY},
        verbose_name=_("default currency"),
        on_delete=models.SET_NULL,
        default=_get_base_currency,
        blank=True,
        null=True,
    )

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("account")
        verbose_name_plural = _("accounts")
        constraints = [models.UniqueConstraint(fields=["name", "parent"], name="unique_account_name_per_parent")]
        ordering = ["name"]

    def __str__(self):
        return f"{self.get_type_display()}:{":".join([account.name for account in self.ancestors(include_self=True)])}"


class Transaction(models.Model):
    """
    Represents a financial transaction record.

    The Transaction class is used to store information about financial transactions, including a description, date, amounts involved, as well as timestamps for record creation and updates.

    :ivar description: Description of the transaction. Can be blank or null.
    :type description: Str
    :ivar date: The date of the transaction. Defaults to the current date.
    :type date: datetime.date
    :ivar amounts: A JSON object holding amounts related to the transaction. Defaults to an empty dictionary.
    :type amounts: Dict
    :ivar created: Timestamp indicating when the transaction record was created. Automatically set.
    :type created: datetime.datetime
    :ivar updated: Timestamp indicating when the transaction record was last updated. Automatically set.
    :type updated: datetime.datetime
    """

    description = models.CharField(_("description"), max_length=250, blank=True, null=True)
    date = models.DateField(_("date"), default=timezone.now)
    amounts = models.JSONField(_("amounts"), default=dict, blank=True, null=True)

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("transaction")
        verbose_name_plural = _("transactions")
        ordering = ["-date"]

    def __str__(self):
        if self.description is not None and self.description != "":
            return f"{self.description} ({self.date.isoformat()})"

        return f"Transaction {self.id} ({self.date.isoformat()})"

    def update_amounts(self) -> None:
        """
        Updates the `amounts` attribute based on the postings associated with the account. The amounts are aggregated per commodity for postings under accounts of type ASSETS.
        The updated `amounts` attribute is then persisted.

        :raises ValueError: If a posting has an invalid or missing attribute.
        :return: None
        """

        amounts = {}

        for posting in self.postings.filter(account__type=Account.AccountTypes.ASSETS):
            if posting.commodity.code in amounts:
                amounts[posting.commodity.code] += posting.amount
            else:
                amounts[posting.commodity.code] = posting.amount

        # Convert Decimal values to strings before saving to JSONField
        serializable_amounts = {currency: str(amount) for currency, amount in amounts.items()}

        self.amounts = serializable_amounts
        self.save()


class Posting(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="postings", verbose_name=_("transaction"))
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="postings", verbose_name=_("account"))

    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2, default=0)
    commodity = models.ForeignKey(
        Commodity, on_delete=models.PROTECT, verbose_name=_("commodity"), default=_get_base_currency, related_name="postings"
    )

    is_balance_posting = models.BooleanField(_("is balance posting"), default=False)

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("posting")
        verbose_name_plural = _("postings")
        ordering = ["transaction", "account"]

    def save(self, *args, **kwargs) -> None:
        if self.amount == Decimal(0):
            self.is_balance_posting = True

        super().save(*args, **kwargs)

    def calculate_balance_amount(self) -> Decimal:
        """
        Calculates the balance amount for the given commodity based on the transaction's postings.

        This method iterates through the transaction's postings, excluding those marked as balance postings, and calculates the balance amount.
        If the posting's commodity matches the specified commodity, its amount is subtracted directly. Otherwise, the posting's amount is converted to the specified commodity before subtraction.

        :return: The calculated balance amount as a Decimal value.
        :rtype: Decimal
        """

        postings = self.transaction.postings.exclude(is_balance_posting=True)
        total = Decimal(0)

        for posting in postings:
            if posting.commodity == self.commodity:
                total -= posting.amount

            else:
                total -= posting.amount * posting.commodity.convert_to(self.commodity)

        return total


# class Posting(models.Model):
#     transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="postings", verbose_name=_("transaction"))
#     account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="postings", verbose_name=_("account"))
#     amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2, default=0)
#     commodity = models.ForeignKey(
#         Commodity, on_delete=models.PROTECT, verbose_name=_("commodity"), default=_get_base_currency, related_name="postings"
#     )
#     converted_amount = models.DecimalField(_("converted amount"), max_digits=10, decimal_places=2, default=0, blank=True, null=True)
#     converted_commodity = models.ForeignKey(
#         Commodity, verbose_name=_("converted commodity"), on_delete=models.PROTECT, blank=True, null=True, related_name="converted_postings"
#     )
#     is_balance_posting = models.BooleanField(_("is balance posting"), default=False)
#
#     created = models.DateTimeField(_("created"), auto_now_add=True)
#     updated = models.DateTimeField(_("updated"), auto_now=True)
#
#     class Meta:
#         verbose_name = _("posting")
#         verbose_name_plural = _("postings")
#         ordering = ["transaction", "account"]
#
#     def __str__(self):
#         return f"{self.transaction} ({self.account.name}): {self.amount} {self.commodity}"
#
#     def save(self, *args, **kwargs):
#         if self.account.default_currency and self.commodity != self.account.default_currency:
#             self.converted_commodity = self.account.default_currency
#             self.converted_amount = self.amount * self.commodity.convert_to(self.account.default_currency)
#
#         else:
#             self.converted_commodity = self.commodity
#             self.converted_amount = self.amount
#
#         if self.amount == Decimal(0):
#             self.is_balance_posting = True
#
#         if self.is_balance_posting:
#             self._calculate_balance_amount()
#
#         super().save(*args, **kwargs)
#
#     def _calculate_balance_amount(self) -> None:
#         other_postings = self.transaction.postings.exclude(id=self.id) if self.id else self.transaction.postings.all()
#
#         total = Decimal(0)
#         for posting in other_postings:
#             if posting.commodity != self.commodity:
#                 converted_amount = posting.amount * posting.commodity.convert_to(self.commodity)
#                 total += converted_amount
#
#             else:
#                 total += posting.amount
#
#         self.amount = -total


# class Posting(models.Model):
#     """
#     Represents a financial posting in a transaction.
#
#     The Posting class models an individual financial posting related to a
#     specific transaction. It includes references to the accounts involved,
#     the amount transacted, the associated commodity, and timestamps for
#     created and updated dates.
#
#     :ivar transaction: The transaction to which this posting belongs.
#     :type transaction: ForeignKey
#     :ivar account: The account involved in this posting.
#     :type account: ForeignKey
#     :ivar amount: The monetary amount associated with this posting.
#     :type amount: DecimalField
#     :ivar commodity: The commodity associated with this posting, such as a
#         currency or other financial unit.
#     :type commodity: ForeignKey
#     :ivar created: The timestamp when this posting was created.
#     :type created: DateTimeField
#     :ivar updated: The timestamp when this posting was last updated.
#     :type updated: DateTimeField
#     """
#
#     transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="postings", verbose_name=_("transaction"))
#     account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="postings", verbose_name=_("account"))
#     amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2, default=0)
#     commodity = models.ForeignKey(
#         Commodity, on_delete=models.PROTECT, verbose_name=_("commodity"), default=_get_base_currency, related_name="postings"
#     )
#     foreign_amount = models.DecimalField(_("foreign amount"), max_digits=10, decimal_places=2, default=0, blank=True, null=True)
#     foreign_commodity = models.ForeignKey(
#         Commodity,
#         verbose_name=_("foreign commodity"),
#         on_delete=models.PROTECT,
#         default=_get_base_currency,
#         blank=True,
#         null=True,
#         related_name="foreign_postings",
#     )
#
#     created = models.DateTimeField(_("created"), auto_now_add=True)
#     updated = models.DateTimeField(_("updated"), auto_now=True)
#
#     class Meta:
#         verbose_name = _("posting")
#         verbose_name_plural = _("postings")
#         ordering = ["transaction", "account"]
#
#     def __str__(self):
#         return f"{self.transaction} ({self.account.name}): {self.amount} {self.commodity}"
#
#     def save(self, *args, **kwargs):
#         if self.amount == Decimal(0):
#             totals = self.transaction.postings.all().values("commodity__code").annotate(total=Sum("amount")).values_list("commodity__code", "total")
#
#             for total in totals:
#                 if total[0] == self.account.default_currency.code:
#                     self.amount -= total[1]
#
#                 else:
#                     self.amount -= total[1] * Commodity.objects.get(code=total[0]).convert_to(self.commodity)
#
#         if self.commodity != self.account.default_currency:
#             self.foreign_amount = self.amount
#             self.foreign_commodity = self.commodity
#
#             self.amount = self.foreign_amount * self.foreign_commodity.convert_to(self.account.default_currency)
#             self.commodity = self.account.default_currency
#
#         super().save(*args, **kwargs)
