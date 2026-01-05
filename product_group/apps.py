from django.apps import AppConfig


class ProductGroupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'product_group'

    def ready(self):
        """
        Import signals when the app is ready.
        This ensures signal handlers are registered.
        """
        import product_group.signals  # noqa
