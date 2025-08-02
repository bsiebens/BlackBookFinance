from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from .backends.base import BaseBackend
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
        Price.objects.create(date=timezone.now().date(), price=Decimal(1.23), commodity=self.eur, unit=self.gbp)
        Price.objects.create(date=timezone.now().date(), price=Decimal(1.50), commodity=self.gbp, unit=self.usd)

        self.assertEqual(self.eur.convert_to(self.usd), Decimal("1.23") * Decimal("1.50"))
        self.assertEqual(self.usd.convert_to(self.eur), (1 / (Decimal("1.50")) * (1 / Decimal("1.23"))))

    def test_convert_to_with_str(self):
        Price.objects.create(date=timezone.now().date(), price=Decimal(1.23), commodity=self.eur, unit=self.usd)

        self.assertEqual(self.eur.convert_to("USD"), Decimal("1.23"))
        self.assertEqual(self.usd.convert_to("EUR"), 1 / Decimal("1.23"))

    def test_convert_to_with_str_not_existing(self):
        self.assertEqual(self.eur.convert_to("CHF"), Decimal("1"))

    def test_convert_to_circular(self):
        Price.objects.create(date=timezone.now().date(), price=Decimal(1.23), commodity=self.eur, unit=self.usd)
        Price.objects.create(date=timezone.now().date(), price=(1 / Decimal(1.23)), commodity=self.usd, unit=self.eur)

        self.assertEqual(self.eur.convert_to(self.gbp), Decimal("1"))


class TestBaseBackend(TestCase):
    def setUp(self):
        self.backend = BaseBackend()
        self.test_commodity = Commodity.objects.create(
            name="Test Commodity", code="TEST", commodity_type=Commodity.CommodityType.CURRENCY, backend=Commodity.Backend.YAHOO, auto_update=True
        )
        self.unit_commodity = Commodity.objects.create(
            name="Test Unit", code="UNIT", commodity_type=Commodity.CommodityType.CURRENCY, backend=Commodity.Backend.YAHOO, auto_update=True
        )
        self.warrant_commodity = Commodity.objects.create(
            name="Warrant", code="WARRANT", commodity_type=Commodity.CommodityType.WARRANT, backend=Commodity.Backend.YAHOO, auto_update=True
        )

    def test_initialization(self):
        self.assertEqual(self.backend.name, "Base Backend")
        self.assertEqual(self.backend.base_currency, "EUR")
        self.assertEqual(self.backend.capabilities, [])
        self.assertEqual(self.backend.backend, "")

    def test_fetch_commodities_all_capabilities(self):
        self.backend.capabilities = ["__all__"]
        self.backend.backend = Commodity.Backend.YAHOO

        result = self.backend._fetch_commodities()

        self.assertEqual(
            result,
            {
                self.test_commodity.code: self.test_commodity,
                self.unit_commodity.code: self.unit_commodity,
                self.warrant_commodity.code: self.warrant_commodity,
            },
        )

    def test_fetch_commodities_filtered_capabilities(self):
        self.backend.capabilities = [Commodity.CommodityType.CURRENCY]
        self.backend.backend = Commodity.Backend.YAHOO

        result = self.backend._fetch_commodities()

        self.assertEqual(result, {self.test_commodity.code: self.test_commodity, self.unit_commodity.code: self.unit_commodity})

    def test_fetch_prices_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.backend._fetch_prices({}, "7d")

    @override_settings(BASE_CURRENCY="USD")
    def test_base_currency_override(self):
        self.assertEqual(BaseBackend().base_currency, "USD")

    @patch("commodities.backends.base.BaseBackend._fetch_prices")
    @patch("commodities.backends.base.BaseBackend._fetch_commodities")
    @patch("commodities.backends.base.Price.objects.bulk_create")
    def test_update_prices(self, mock_bulk_create, mock_fetch_commodities, mock_fetch_prices):
        mock_fetch_commodities.return_value = {self.test_commodity.code: self.test_commodity}
        mock_fetch_prices.return_value = [{"date": "2025-08-01", "price": 100.0, "commodity": self.test_commodity, "unit": self.test_commodity}]

        self.backend.update_prices("7d")

        mock_fetch_commodities.assert_called_once()
        mock_fetch_prices.assert_called_once_with(commodities={self.test_commodity.code: self.test_commodity}, period="7d")
        mock_bulk_create.assert_called_once()
