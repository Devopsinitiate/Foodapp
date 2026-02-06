from django.apps import AppConfig

class RestaurantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurants'
    verbose_name = 'Restaurant Management'
    
    def ready(self):
        """Import signals when app is ready."""
        # import restaurants.signals
        pass