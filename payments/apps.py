from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payments'
    verbose_name = 'Payment Processing'
    
    def ready(self):
        """Import signals when app is ready."""
        # import payments.signals
        pass