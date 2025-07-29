from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class Commodity(models.Model):
    """
    A commodity represents something that can be bought or sold, including currencies, stocks, ...

    :ivar name: The name of the commodity.
    :type name: str
    """
    
    name = models.CharField(_("name"), max_length=100)
    code = models.CharField(_("code"), max_length=10)
    
    class Meta:
        verbose_name = _("commodity")
        verbose_name_plural = _("commodities")
        ordering = ["name", "code"]
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
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
    :type price: decimal.Decimal
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