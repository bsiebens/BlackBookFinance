from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money
from tree_queries.models import TreeNode

from commodities.models import Commodity


def _get_base_currency():
    name, code = getattr(settings, "BASE_CURRENCY", ("Euro", "EUR"))
    base_currency, _ = Commodity.objects.get_or_create(name=name, code=code, commodity_type=Commodity.CommodityTypes.CURRENCY)

    return base_currency.id


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
        on_delete=models.PROTECT,
        default=_get_base_currency,
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

    @property
    def balance(self) -> Money:
        """
        Retrieve the total balance of the account based on the aggregated number of all postings.

        :return: The total balance as a Money object, representing the sum of postings in the account.
        :rtype: Money
        """

        amounts = {}
        commodity_totals = self.postings.values("commodity__code").annotate(total=Sum("amount"))

        for commodity in commodity_totals:
            if commodity["commodity__code"] in amounts:
                amounts[commodity["commodity__code"]] += commodity["total"]
            else:
                amounts[commodity["commodity__code"]] = commodity["total"]

        if self.default_currency.code not in amounts:
            amounts[self.default_currency.code] = Decimal(0)

        for code, amount in amounts.items():
            if code != self.default_currency.code and code is not None:
                amounts[self.default_currency.code] += amount * Commodity.objects.get(code=code).convert_to(self.default_currency.code)

        return Money(amounts[self.default_currency.code], self.default_currency.code)


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

    @property
    def balance(self) -> Money:
        """
        Calculates the total balance in terms of a base currency by aggregating
        all related postings and converting amounts as necessary.

        This property computes the balance using all postings associated. It
        aggregates amounts for each commodity and converts them into the base
        currency using predefined conversion rates. The result is returned
        as a `Money` object that encapsulates the final balance and its
        currency.

        :return: An instance of the `Money` class representing the total
                 balance in the base currency.
        :rtype: Money
        """

        amounts = {}
        base_currency = Commodity.objects.get(id=_get_base_currency())
        commodity_totals = self.postings.filter(account__type=Account.AccountTypes.ASSETS).values("commodity__code").annotate(total=Sum("amount"))

        for commodity in commodity_totals:
            if commodity["commodity__code"] in amounts:
                amounts[commodity["commodity__code"]] += commodity["total"]
            else:
                amounts[commodity["commodity__code"]] = commodity["total"]

        if base_currency.code not in amounts:
            amounts[base_currency.code] = Decimal(0)

        for code, amount in amounts.items():
            if code != base_currency.code and code is not None:
                amounts[base_currency.code] += amount * Commodity.objects.get(code=code).convert_to(base_currency.code)

        return Money(amounts[base_currency.code], base_currency.code)


class Posting(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="postings", verbose_name=_("transaction"))
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="postings", verbose_name=_("account"))

    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2, default=0)
    commodity = models.ForeignKey(
        Commodity, on_delete=models.PROTECT, verbose_name=_("commodity"), default=_get_base_currency, related_name="postings"
    )
    foreign_amount = models.DecimalField(_("foreign amount"), max_digits=10, decimal_places=2, default=0, blank=True, null=True)
    foreign_commodity = models.ForeignKey(
        Commodity,
        verbose_name=_("foreign commodity"),
        default=_get_base_currency,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="foreign_postings",
    )

    is_balance_posting = models.BooleanField(_("is balance posting"), default=False)

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("posting")
        verbose_name_plural = _("postings")
        ordering = ["transaction", "account"]

    def clean(self) -> None:
        super().clean()

        if not self.account.id:
            return

        if self.commodity != self.account.default_currency:
            if self.foreign_commodity != self.account.default_currency and (
                self.foreign_commodity is None or self.foreign_commodity != self.account.default_currency
            ):
                raise ValidationError(
                    {
                        "commodity": _(
                            "Either the commodity or the foreign commodity must be the equal to the account's default currency ({})"
                        ).format(self.account.default_currency.code),
                        "foreign_commodity": _(
                            "Either the commodity or the foreign commodity must be the equal to the account's default currency ({})"
                        ).format(self.account.default_currency.code),
                    }
                )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()

        if self.commodity != self.account.default_currency:
            foreign_amount = self.amount
            foreign_commodity = self.commodity

            if self.foreign_amount == Decimal(0):
                self.amount = foreign_amount * foreign_commodity.convert_to(self.account.default_currency)
                self.commodity = self.account.default_currency

            else:
                self.amount = self.foreign_amount
                self.commodity = self.foreign_commodity

            self.foreign_amount = foreign_amount
            self.foreign_commodity = foreign_commodity

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
