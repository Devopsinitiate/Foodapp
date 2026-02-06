from django.apps import AppConfig

class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery'
    verbose_name = 'Delivery Tracking'
    
    def ready(self):
        """Import signals when app is ready."""
        import delivery.signals