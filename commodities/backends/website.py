import requests
from django.db.models import Max
from django.utils import timezone
from lxml import html

from .base import BaseBackend
from ..models import Commodity, Price


class WebsiteBackend(BaseBackend):
    name = "Website Scraper"
    capabilities = ["__all__"]
    backend = Commodity.Backend.WEBSITE

    def _fetch_prices(self, commodities: dict[str, Commodity], period: str) -> list[dict]:
        latest_dates = {
            entry["commodity__code"]: entry["latest_date"]
            for entry in Price.objects.filter(backend=self.name, commodity__code__in=commodities.keys())
            .values("commodity__code")
            .annotate(latest_date=Max("date"))
        }

        prices = []

        for commodity_code, commodity in commodities.items():
            if commodity_code not in latest_dates or latest_dates[commodity_code] < timezone.now().date():
                response = requests.get(commodity.website)

                if response.status_code == 200:
                    tree = html.fromstring(response.content)

                    prices.append(
                        {
                            "commodity": commodity,
                            "price": (
                                float(tree.xpath(commodity.xpath_selector_amount)[0].text)
                                if commodity.xpath_selector_amount != "" and commodity.xpath_selector_amount is not None
                                else float(tree.text)
                            ),
                            "unit": commodity.website_currency,
                            "date": timezone.now().date(),
                        }
                    )

        return prices
