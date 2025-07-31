from decimal import Decimal
from time import timezone

import pandas as pd
import yfinance as yf
from django.db.models import Max
from django.utils import timezone

from .base import BaseBackend
from ..models import Commodity, Price


class YahooFinanceBackend(BaseBackend):
    name = "Yahoo Finance"
    capabilities = [Commodity.CommodityType.CURRENCY]
    backend = Commodity.Backend.YAHOO

    def fetch_prices(self, period: str) -> list[dict]:
        # Step 1: fetch all commodities linked to this backend
        commodities = {
            commodity.code: commodity
            for commodity in Commodity.objects.filter(commodity_type__in=self.capabilities, backend=self.backend, auto_update=True)
        }

        unit = commodities[self.base_currency] if self.base_currency in commodities else Commodity.objects.get(code=self.base_currency)

        # Step 2: get the latest rates in the databse for each commodity
        latest_dates = {
            entry["commodity__code"]: entry["latest_date"]
            for entry in Price.objects.filter(backend=self.name, commodity__code__in=commodities.keys(), unit=unit)
            .values("commodity__code")
            .annotate(latest_date=Max("date"))
        }

        # Step 3: prepare tickers for Yahoo Finance API Call
        tickers = [f"{code}{self.base_currency}=X" for code in commodities.keys() if code != self.base_currency]

        # Step 4: fetch data
        ticker_data = yf.download(tickers=tickers, period=period, progress=False, auto_adjust=True)
        if ticker_data.empty:
            return []

        # Step 5: process the downloaded data
        prices = []
        today = timezone.now().date()

        if isinstance(ticker_data.columns, pd.MultiIndex):
            close_prices = ticker_data.get("Close")
        else:
            close_prices = ticker_data[["Close"]]
            close_prices.columns = [tickers[0]]

        if close_prices is None or close_prices.empty:
            return []

        for commodity_code, commodity_object in commodities.items():
            if commodity_code == self.base_currency:
                continue

            ticker = f"{commodity_code}{self.base_currency}=X"
            if ticker not in close_prices.columns:
                continue

            price_series = close_prices[ticker].dropna()
            last_db_date = latest_dates.get(commodity_code)

            if last_db_date:
                price_series = price_series[price_series.index.date > last_db_date]
            price_series = price_series[price_series.index.date < today]

            for rate_date_ts, rate_val in price_series.items():
                prices.append({"commodity": commodity_object, "unit": unit, "price": Decimal(str(rate_val)), "date": rate_date_ts.date()})

        return prices
