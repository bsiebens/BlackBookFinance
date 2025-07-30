from collections import defaultdict, deque
from django.db.models import Max
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal

class Commodity(models.Model):
    """
    A commodity represents something that can be bought or sold, including currencies, stocks, ...

    :ivar name: The name of the commodity.
    :type name: Str
    :ivar code: A code for the commodity (e.g., EUR, USD, META, ...)
    :type code: str
    """
    
    name = models.CharField(_("name"), max_length=100)
    code = models.CharField(_("code"), max_length=10)
    
    class Meta:
        verbose_name = _("commodity")
        verbose_name_plural = _("commodities")
        ordering = ["name", "code"]
    
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
        for entry in latest_dates:
            commodity = entry["commodity"]
            unit = entry["unit"]
            date = entry["latest_date"]
            
            price = Price.objects.filter(commodity=commodity, unit=unit, date=date).latest()
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
    
    created = models.DateTimeField(_("created"), auto_now_add=True)
    updated = models.DateTimeField(_("updated"), auto_now=True)
    
    class Meta:
        verbose_name = _("price")
        verbose_name_plural = _("prices")
        ordering = ["-date"]
        
    def __str__(self):
        return f"{self.commodity}: {self.price} {self.unit} @ {self.date}"