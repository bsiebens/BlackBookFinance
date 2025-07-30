from django.test import TestCase

from .models import Commodity


class CommodityTestCase(TestCase):
    def setUp(self):
        self.eur = Commodity.objects.create(name="Euro", code="EUR")
        self.usd = Commodity.objects.create(name="US Dollar", code="USD")
        self.gbp = Commodity.objects.create(name="Pound Sterling", code="GBP")

    def test_str(self):
        self.assertEqual(str(self.eur), "Euro (EUR)")

    def test_convert_to_no_rates(self): ...

    def test_convert_to_direct(self): ...

    def test_convert_to_indirect(self): ...

    def test_convert_to_with_str(self): ...

    def test_convert_to_with_str_not_existing(self): ...

    def test_convert_to_circular(self): ...
