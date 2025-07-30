from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from .models import Commodity, Price


class CommodityTestCase(TestCase):
    def setUp(self):
        self.eur = Commodity.objects.create(name="Euro", code="EUR")
        self.usd = Commodity.objects.create(name="US Dollar", code="USD")
        self.gbp = Commodity.objects.create(name="Pound Sterling", code="GBP")

    def test_str(self):
        self.assertEqual(str(self.eur), "Euro (EUR)")

    def test_convert_to_no_rates(self):
        self.assertEqual(self.eur.convert_to(self.usd), Decimal(1.0))

    def test_convert_to_direct(self):
        Price.objects.create(date=timezone.now().date(), price=Decimal(1.23), commodity=self.eur, unit=self.usd)
        self.assertEqual(self.eur.convert_to(self.usd), Decimal("1.23"))
        self.assertEqual(self.usd.convert_to(self.eur), 1 / Decimal("1.23"))

    def test_convert_to_indirect(self):
        raise NotImplementedError

    def test_convert_to_with_str(self):
        raise NotImplementedError

    def test_convert_to_with_str_not_existing(self):
        raise NotImplementedError

    def test_convert_to_circular(self):
        raise NotImplementedError
