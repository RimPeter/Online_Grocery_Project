from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = '_catalog'
    
    def ready(self):
        # Import signals here to ensure they are registered when the app is ready
        import _catalog.signals

