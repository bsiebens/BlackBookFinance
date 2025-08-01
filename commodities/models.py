from collections import defaultdict, deque
from decimal import Decimal

from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Commodity(models.Model):
    """
    A commodity represents something that can be bought or sold, including currencies, stocks, ...

    :ivar name: The name of the commodity.
    :type name: Str
    :ivar code: A code for the commodity (e.g., EUR, USD, META, ...)
    :type code: str
    """

    class CommodityType(models.TextChoices):
        CURRENCY = "currency", _("Currency")
        STOCK = "stock", _("Stock")
        FUND = "fund", _("Fund")
        WARRANT = "warrant", _("Warrant")
        ASSET = "asset", _("Asset")
        OTHER = "other", _("Other")

    class Backend(models.TextChoices):
        YAHOO = "yahoo", _("Yahoo Finance")
        WEBSITE = "website", _("Website Scraper")
        CUSTOM = "custom", _("Custom")

    name = models.CharField(_("name"), max_length=100)
    code = models.CharField(_("code"), max_length=10, unique=True)  # Add unique constraint

    commodity_type = models.CharField(_("commodity type"), choices=CommodityType.choices, default=CommodityType.OTHER, max_length=10)
    backend = models.CharField(_("backend"), choices=Backend.choices, default=Backend.YAHOO, max_length=10, blank=True, null=True)
    auto_update = models.BooleanField(_("auto update"), default=False)
    website = models.URLField(_("website"), blank=True, null=True)
    xpath_selector_amount = models.CharField(_("xpath selector amount"), max_length=255, blank=True, null=True)
    website_currency = models.ForeignKey("Commodity", verbose_name=_("website currency"), on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        verbose_name = _("commodity")
        verbose_name_plural = _("commodities")
        ordering = ["name", "code"]
        constraints = [models.UniqueConstraint(fields=["name", "code"], name="unique_commodity")]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def convert_to(self, commodity: "str | Commodity") -> Decimal:
        """
        Converts this commodity into the given commodity.

        :param commodity: The commodity to convert to
        :type commodity: str | Commodity
        :return: The conversion rate for converting this commodity into the given commodity
        :rtype: decimal.Decimal
        """

        if not isinstance(commodity, Commodity):
            try:
                commodity = Commodity.objects.get(code=commodity)

            except Commodity.DoesNotExist:
                return Decimal(1.0)

        graph = defaultdict(list)
        prices_lookup = {}

        # Step 1: find the latest dates
        latest_dates = Price.objects.values("commodity", "unit").annotate(latest_date=Max("date"))

        # Step 2: fetch most recent prices
        # Replace the inefficient loop with a single query:
        latest_prices = Price.objects.filter(
            commodity__in=[entry["commodity"] for entry in latest_dates],
            unit__in=[entry["unit"] for entry in latest_dates],
            date__in=[entry["latest_date"] for entry in latest_dates],
        ).select_related("commodity", "unit")

        # Build the graph more efficiently
        for price in latest_prices:
            graph[price.commodity].append(price.unit)
            prices_lookup[(price.commodity, price.unit)] = price.price

            if price.price != Decimal(0.0):
                graph[price.unit].append(price.commodity)
                prices_lookup[(price.unit, price.commodity)] = Decimal(1.0) / price.price

        # Step 3: breadth-first search (BFS)
        queue = deque([(self, [self], Decimal(1.0))])
        visited = set()

        while queue:
            current, path, factor = queue.popleft()
            if current == commodity:
                return factor

            visited.add(current)

            for neighbor in graph[current]:
                if neighbor not in visited:
                    new_factor = factor * prices_lookup[(current, neighbor)]
                    queue.append((neighbor, path + [neighbor], new_factor))

        return Decimal(1.0)


class Price(models.Model):
    """
    Represents the pricing details of a specific commodity.

    This class is used to store pricing information including the date, the price value,
    the commodity associated with the price, and the unit of measurement. It also maintains
    timestamps for creation and last update. Instances of this class are typically ordered
    by their date in descending order.

    :ivar date: The date of the price entry.
    :type date: datetime.date
    :ivar price: The price value of the commodity.
    :type price: Decimal.Decimal
    :ivar commodity: The commodity for which the price is applicable.
    :type commodity: Commodity
    :ivar unit: The unit of measurement for the price value.
    :type unit: Commodity
    :ivar created: Timestamp when the price entry was created.
    :type created: datetime.datetime
    :ivar updated: Timestamp of the last update to the price entry.
    :type updated: datetime.datetime
    """

    date = models.DateField(_("date"), default=timezone.now)
    price = models.DecimalField(_("price"), max_digits=20, decimal_places=5)
    commodity = models.ForeignKey(Commodity, on_delete=models.CASCADE, related_name="prices", verbose_name=_("commodity"))
    unit = models.ForeignKey(Commodity, on_delete=models.CASCADE, verbose_name=_("unit"), help_text=_("The unit of this price."))
    backend = models.CharField(_("backend"), max_length=250, default="Manual")

    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        verbose_name = _("price")
        verbose_name_plural = _("prices")
        ordering = ["-date"]
        get_latest_by = "date"
        constraints = [
            models.UniqueConstraint(fields=["commodity", "unit", "date", "backend"], name="unique_price_per_day"),
            models.CheckConstraint(check=models.Q(price__gt=0), name="positive_price"),
        ]

    def __str__(self):
        return f"{self.commodity}: {self.price} {self.unit} @ {self.date}"
