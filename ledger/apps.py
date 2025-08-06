from django.apps import AppConfig


class LedgerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ledger"

    def ready(self):
        try:
            # noinspection PyUnresolvedReferences
            import ledger.signals  # noqa
        except ImportError:
            pass
