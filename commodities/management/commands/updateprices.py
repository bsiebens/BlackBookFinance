from django.core.management.base import BaseCommand

from ...backends.website import WebsiteBackend
from ...backends.yahoo import YahooFinanceBackend


class Command(BaseCommand):
    help = "Update prices in the database using the different backends."

    def add_arguments(self, parser):
        parser.add_argument("--period", type=str, default="7d", help="Time period for updating prices (e.g., 7d, 30d, 1y). Default is 7d.")

    def handle(self, *args, **options):
        backends = [YahooFinanceBackend(), WebsiteBackend()]
        period = options["period"]

        self.stdout.write("\nUpdating prices database ...")

        max_name_length = max(len(backend.name) for backend in backends)
        dots_padding = 3
        total_width = max_name_length + dots_padding

        for backend in backends:
            dots_needed = total_width - len(backend.name)
            backend_text = f"{backend.name} {"." * dots_needed}"
            self.stdout.write("  - " + backend_text, ending="")

            try:
                backend.update_prices(period=period)
                self.stdout.write(self.style.SUCCESS(" done"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f" failed: {str(e)}"))
