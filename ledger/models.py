from django.db import models
from django.utils.translation import gettext_lazy as _
from tree_queries.models import TreeNode

from commodities.models import Commodity


class Bank(models.Model):
    """
    Represents a bank entity used in financial or organizational contexts.

    This class defines the structure and behavior of a bank, allowing
    it to be uniquely identified by its name. It supports Django's ORM
    functionality by inheriting from the `models.Model` class and includes
    localization support for internationalized applications.

    :ivar name: The unique name of the bank.
    :type name: str
    """

    name = models.CharField(_("name"), max_length=250, unique=True, db_index=True)

    class Meta:
        verbose_name = _("bank")
        verbose_name_plural = _("banks")
        ordering = ["name"]

    def __str__(self):
        return self.name


class Account(TreeNode):
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
        blank=True,
        null=True,
    )
    calculated_name = models.CharField(_("calculated name"), max_length=1000, blank=True, editable=False)

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("account")
        verbose_name_plural = _("accounts")
        constraints = [models.UniqueConstraint(fields=["name", "parent"], name="unique_account_name_per_parent")]
        ordering = ["name"]
