from django.conf import settings
from django.db.transaction import atomic

from ..models import Price, Commodity


class BaseBackend(object):
    """
    Base class defining the structure and common properties for backend implementations.

    This class serves as a foundational base for implementing specific backend subclasses.
    It provides attributes such as `name`, which identifies the backend, `base_currency`,
    which defines a default currency setting, and `capabilities`, which offers a list of
    functional capabilities supported by the backend. This design allows extending and
    customizing backend behaviors as per requirements.

    :ivar name: The name identifying the backend.
    :type name: Str
    :ivar base_currency: The default currency for operations, with a fallback to EUR.
    :type base_currency: Str
    :ivar capabilities: A list of capabilities supported by the backend.
    :type capabilities: List[str]
    :ivar backend: The backend option linked on the Commodity model.
    :type backend: Str
    """

    name: str = "Base Backend"
    base_currency: str = getattr(settings, "BASE_CURRENCY", "EUR")
    capabilities: list[str] = []
    backend: str = ""

    def _fetch_commodities(self) -> dict[str, Commodity]:
        """
        Fetches commodities from the available database based on specific filters.

        This method retrieves a dictionary of commodities filtered by the given
        capabilities, backend, and auto-update status. It uses the Commodity model to
        query for matching database entries. Each commodity is keyed by its unique
        code, ensuring easy access to individual commodity objects.

        :return: A dictionary mapping commodity codes to corresponding Commodity objects.
        :rtype: dict[str, Commodity]
        """

        commodities = Commodity.objects.filter(backend=self.backend, auto_update=True).select_related("website_currency")

        if self.capabilities[0] != "__all__":
            commodities = commodities.filter(commodity_type__in=self.capabilities)

        return {commodity.code: commodity for commodity in commodities}

    def _fetch_prices(self, commodities: dict[str, Commodity], period: str) -> list[dict]:
        """
        Fetches price data for the specified period.

        This method is intended to provide price data over a specific time
        frame. Currently, it serves as a placeholder and requires
        implementation. The returned price data will be in the form of a list
        of dictionary objects, where each dictionary represents a record of
        price information.

        :param commodities: The list of commodities that need to be fetched.
        :type commodities: Dict[str, Commodity]
        :param period: The time frame for which price data is requested.
        :type period: Str
        :return: A list of dictionaries containing price data for the specified
            period.
        :rtype: List[dict]
        """
        raise NotImplementedError

    @atomic
    def update_prices(self, period: str = "7d", base_currency: "str | None" = None) -> None:
        """
        Update prices for a specific period and base currency.

        This method updates financial or market data prices for a defined
        timeframe (period) and an optional base currency. The period should
        be specified as a string, e.g., "7d" for 7 days, which determines
        the length of historical or forecast data being updated. If no base
        currency is specified, the default currency configuration will be used.

        :param period: The duration for which prices should be updated
                       (e.g., "7d" for 7 days).
        :type period: Str

        :param base_currency: The currency in which the prices should be
                              updated. Defaults to None. If None, a default
                              base currency is used.
        :type base_currency: Str | None
        """

        if base_currency is None:
            base_currency = self.base_currency

        commodities = self._fetch_commodities()
        new_prices = self._fetch_prices(commodities=commodities, period=period)

        Price.objects.bulk_create(
            [
                Price(date=new_price["date"], commodity=new_price["commodity"], unit=new_price["unit"], price=new_price["price"], backend=self.name)
                for new_price in new_prices
            ]
        )
