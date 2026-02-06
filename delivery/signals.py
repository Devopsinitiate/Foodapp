"""Signals for delivery app"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from users.models import User


@receiver(post_save, sender=User)
def create_driver_availability(sender, instance, created, **kwargs):
    """
    Automatically create DriverAvailability record when a driver is verified.
    """
    # Avoid circular import
    from delivery.models import DriverAvailability
    
    # Only for drivers who are verified
    if instance.is_driver and instance.is_verified_driver:
        # Create availability record if it doesn't exist
        DriverAvailability.objects.get_or_create(
            driver=instance,
            defaults={
                'is_online': False,
                'is_available': True,
                'average_rating': 5.0,
            }
        )
