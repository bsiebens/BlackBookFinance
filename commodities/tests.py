from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pandas as pd
from django.test import TestCase, override_settings
from django.utils import timezone

from .backends.base import BaseBackend
from .backends.website import WebsiteBackend
from .backends.yahoo import YahooFinanceBackend
from .models import Commodity, Price


class CommodityTestCase(TestCase):
    def setUp(self):
        self.eur, _ = Commodity.objects.get_or_create(name="Euro", code="EUR")
        self.usd, _ = Commodity.objects.get_or_create(name="US Dollar", code="USD")
        self.gbp, _ = Commodity.objects.get_or_create(name="Pound Sterling", code="GBP")

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
        self.test_commodity, _ = Commodity.objects.get_or_create(
            name="Test Commodity", code="TEST", commodity_type=Commodity.CommodityTypes.CURRENCY, backend=Commodity.Backend.YAHOO, auto_update=True
        )
        self.unit_commodity, _ = Commodity.objects.get_or_create(
            name="Test Unit", code="UNIT", commodity_type=Commodity.CommodityTypes.CURRENCY, backend=Commodity.Backend.YAHOO, auto_update=True
        )
        self.warrant_commodity, _ = Commodity.objects.get_or_create(
            name="Warrant", code="WARRANT", commodity_type=Commodity.CommodityTypes.WARRANT, backend=Commodity.Backend.YAHOO, auto_update=True
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
        self.backend.capabilities = [Commodity.CommodityTypes.CURRENCY]
        self.backend.backend = Commodity.Backend.YAHOO

        result = self.backend._fetch_commodities()

        self.assertEqual(result, {self.test_commodity.code: self.test_commodity, self.unit_commodity.code: self.unit_commodity})

    def test_fetch_prices_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.backend._fetch_prices({}, "7d")

    @override_settings(BASE_CURRENCY=("US Dollar", "USD"))
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


class TestYahooFinanceBackend(TestCase):
    def setUp(self):
        self.backend = YahooFinanceBackend()

        defaults = {"backend": Commodity.Backend.YAHOO, "auto_update": True}
        create_defaults = defaults.copy()

        # Create sample commodities
        self.commodity1, _ = Commodity.objects.update_or_create(
            name="Euro", code="EUR", commodity_type=Commodity.CommodityTypes.CURRENCY, defaults=defaults, create_defaults=create_defaults
        )
        self.commodity2, _ = Commodity.objects.update_or_create(
            name="British Pound", code="GBP", commodity_type=Commodity.CommodityTypes.CURRENCY, defaults=defaults, create_defaults=create_defaults
        )
        # Create a unit for commodities
        self.unit, _ = Commodity.objects.get_or_create(name="US Dollar", code="USD", commodity_type=Commodity.CommodityTypes.CURRENCY)

    @override_settings(BASE_CURRENCY=("US Dollar", "USD"))
    @patch("commodities.backends.yahoo.yf.download")
    def test_fetch_prices_empty_response(self, mock_yf_download):
        mock_yf_download.return_value = MagicMock(empty=True)
        commodities = {self.commodity1.code: self.commodity1, self.commodity2.code: self.commodity2}
        result = self.backend._fetch_prices(commodities, period="7d")
        self.assertEqual(result, [])

    @override_settings(BASE_CURRENCY=("US Dollar", "USD"))
    @patch("commodities.backends.yahoo.yf.download")
    def test_fetch_prices_successful_response(self, mock_yf_download):
        # Create the proper datetime index for the mock DataFrame
        dates = pd.date_range(start=timezone.now().date() - timedelta(days=2), end=timezone.now().date() - timedelta(days=1), freq="D")
        # Create mock DataFrame with proper structure
        mock_data = pd.DataFrame({"EURUSD=X": [1.1, 1.2], "GBPUSD=X": [1.3, 1.4]}, index=dates)

        # Create the mock with the proper MultiIndex columns structure
        mock_df = pd.DataFrame()
        mock_df[("Close", "EURUSD=X")] = mock_data["EURUSD=X"]
        mock_df[("Close", "GBPUSD=X")] = mock_data["GBPUSD=X"]
        # noinspection PyTypeChecker
        mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)
        mock_df.index = dates

        # Set up the mock return value
        mock_yf_download.return_value = mock_df

        commodities = {self.commodity1.code: self.commodity1, self.commodity2.code: self.commodity2, "USD": self.unit}
        result = self.backend._fetch_prices(commodities, period="7d")

        self.assertGreater(len(result), 0)
        self.assertTrue(all("commodity" in entry and "price" in entry and "date" in entry for entry in result))


class TestWebsiteBackendFetchPrices(TestCase):
    def setUp(self):
        self.currency = Commodity.objects.create(name="USD", code="USD", commodity_type=Commodity.CommodityTypes.CURRENCY)
        self.commodity = Commodity.objects.create(
            name="Gold",
            code="GOLD",
            backend=Commodity.Backend.WEBSITE,
            website="http://example.com",
            xpath_selector_amount="//price",
            website_currency=self.currency,
        )
        self.price = Price.objects.create(
            date=timezone.now().date() - timedelta(days=1),
            price=Decimal("2000.00"),
            commodity=self.commodity,
            unit=self.currency,
            backend=WebsiteBackend.name,
        )

    @patch("requests.get")
    def test_fetch_prices_update_existing_commodity_price(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<price>2050.00</price>"

        backend = WebsiteBackend()
        prices = backend._fetch_prices({"GOLD": self.commodity}, "daily")

        self.assertEqual(len(prices), 1)
        self.assertEqual(prices[0]["price"], 2050.00)
        self.assertEqual(prices[0]["commodity"], self.commodity)
        self.assertEqual(prices[0]["unit"], self.currency)
        self.assertEqual(prices[0]["date"], timezone.now().date())

    @patch("requests.get")
    def test_fetch_prices_skip_if_latest_price_exists(self, mock_get):
        # Create a price for today to test the skip logic
        Price.objects.create(
            date=timezone.now().date(), price=Decimal("2050.00"), commodity=self.commodity, unit=self.currency, backend=WebsiteBackend.name
        )

        backend = WebsiteBackend()
        prices = backend._fetch_prices({"GOLD": self.commodity}, "daily")

        self.assertEqual(len(prices), 0)
        # Verify that requests.get was never called since we should skip fetching
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_fetch_prices_no_response_from_website(self, mock_get):
        mock_get.return_value.status_code = 404

        backend = WebsiteBackend()
        prices = backend._fetch_prices({"GOLD": self.commodity}, "daily")

        self.assertEqual(len(prices), 0)

    @patch("requests.get")
    def test_fetch_prices_invalid_xpath_selector(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"<invalid>2050.00</invalid>"

        backend = WebsiteBackend()
        with self.assertRaises(IndexError):  # XPath fails if no valid node is found
            backend._fetch_prices({"GOLD": self.commodity}, "daily")
