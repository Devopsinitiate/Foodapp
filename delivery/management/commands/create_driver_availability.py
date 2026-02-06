"""Management command to create missing DriverAvailability records"""
from django.core.management.base import BaseCommand
from users.models import User
from delivery.models import DriverAvailability


class Command(BaseCommand):
    help = 'Create DriverAvailability records for drivers who don\'t have one'

    def handle(self, *args, **options):
        self.stdout.write("Creating missing DriverAvailability records...")
        
        # Get all verified drivers
        drivers = User.objects.filter(
            is_driver=True,
            is_verified_driver=True,
            is_active=True
        )
        
        created_count = 0
        updated_count = 0
        
        for driver in drivers:
            availability, created = DriverAvailability.objects.get_or_create(
                driver=driver,
                defaults={
                    'is_online': False,
                    'is_available': True,
                    'current_latitude': None,
                    'current_longitude': None,
                    'average_rating': 5.0,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created DriverAvailability for {driver.email}")
                )
            else:
                updated_count += 1
                self.stdout.write(f"  Already exists for {driver.email}")
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Created: {created_count} records"))
        self.stdout.write(f"Existing: {updated_count} records")
        self.stdout.write("=" * 60)
        
        if created_count > 0:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  Drivers need to log in and click 'Go Online' to be available for deliveries!"
            ))
