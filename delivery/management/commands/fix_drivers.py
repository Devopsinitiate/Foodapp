"""Management command to fix driver assignment issues"""
from django.core.management.base import BaseCommand
from django.db import models
from decimal import Decimal


class Command(BaseCommand):
    help = 'Diagnose and fix driver assignment issues'

    def handle(self, *args, **options):
        # Import here to avoid circular dependency
        from users.models import User
        from delivery.models import DriverAvailability
        from restaurants.models import Restaurant
        from orders.models import Order
        
        self.stdout.write("=" * 70)
        self.stdout.write("DRIVER ASSIGNMENT DIAGNOSTIC & AUTO-FIX")
        self.stdout.write("=" * 70)

        # Step 1: Check verified drivers
        self.stdout.write("\n[STEP 1] Checking Verified Drivers...")
        drivers = User.objects.filter(
            is_driver=True,
            is_verified_driver=True,
            is_active=True
        )
        self.stdout.write(f"✓ Found {drivers.count()} verified, active drivers")
        for driver in drivers:
            self.stdout.write(f"  - {driver.email} (ID: {driver.id})")

        if drivers.count() == 0:
            self.stdout.write(self.style.ERROR("\n❌ PROBLEM: No verified drivers found!"))
            self.stdout.write("   FIX: Go to Django admin and set is_verified_driver=True for drivers")
            return

        # Step 2: Check/Create DriverAvailability records
        self.stdout.write("\n[STEP 2] Checking DriverAvailability Records...")
        created_count = 0
        for driver in drivers:
            availability, created = DriverAvailability.objects.get_or_create(
                driver=driver,
                defaults={
                    'is_online': False,
                    'is_available': True,
                    'average_rating': Decimal('5.0'),
                    'current_latitude': None,
                    'current_longitude': None,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Created DriverAvailability for {driver.email}"))
                created_count += 1
            else:
                self.stdout.write(f"  - Already exists for {driver.email}")
                self.stdout.write(f"    Online: {availability.is_online}, Available: {availability.is_available}")
                self.stdout.write(f"    GPS: lat={availability.current_latitude}, lon={availability.current_longitude}")

        # Step 3: Check online status
        self.stdout.write("\n[STEP 3] Checking Driver Online Status...")
        online_drivers = DriverAvailability.objects.filter(
            is_online=True,
            is_available=True,
            driver__is_verified_driver=True,
            driver__is_active=True
        )
        self.stdout.write(f"Drivers currently ONLINE: {online_drivers.count()}")

        if online_drivers.count() == 0:
            self.stdout.write(self.style.WARNING("\n⚠️  WARNING: No drivers are online!"))
            self.stdout.write("   SOLUTION: Drivers must:")
            self.stdout.write("   1. Log in to driver dashboard")
            self.stdout.write("   2. Click 'Go Online' button")
            self.stdout.write("   3. Allow browser location access")
            self.stdout.write("\n   OR manually set online in Django admin")

        # Step 4: Check GPS coordinates
        self.stdout.write("\n[STEP 4] Checking Driver GPS Coordinates...")
        drivers_with_gps = DriverAvailability.objects.filter(
            is_online=True,
            current_latitude__isnull=False,
            current_longitude__isnull=False
        )
        self.stdout.write(f"Online drivers WITH GPS: {drivers_with_gps.count()}")

        if drivers_with_gps.count() == 0 and online_drivers.count() > 0:
            self.stdout.write(self.style.WARNING("\n⚠️  Setting default GPS coordinates..."))
            for availability in online_drivers:
                if not availability.current_latitude or not availability.current_longitude:
                    availability.current_latitude = Decimal('6.5244')
                    availability.current_longitude = Decimal('3.3792')
                    availability.save()
                    self.stdout.write(self.style.SUCCESS(f"   ✓ Set default GPS for {availability.driver.email}"))

        # Step 5: Check restaurant coordinates
        self.stdout.write("\n[STEP 5] Checking Restaurant Coordinates...")
        restaurants_without_coords = Restaurant.objects.filter(
            models.Q(latitude__isnull=True) | models.Q(longitude__isnull=True)
        )

        if restaurants_without_coords.exists():
            self.stdout.write(self.style.WARNING(f"⚠️  Setting coordinates for {restaurants_without_coords.count()} restaurants..."))
            for restaurant in restaurants_without_coords:
                restaurant.latitude = Decimal('6.5244')
                restaurant.longitude = Decimal('3.3792')
                restaurant.save()
                self.stdout.write(self.style.SUCCESS(f"   ✓ Set default GPS for {restaurant.name}"))
        else:
            self.stdout.write(self.style.SUCCESS("✓ All restaurants have coordinates"))

        # Summary
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS(f"✓ {drivers.count()} verified drivers"))
        self.stdout.write(self.style.SUCCESS(f"✓ {DriverAvailability.objects.filter(driver__in=drivers).count()} DriverAvailability records"))
        
        if online_drivers.count() > 0:
            self.stdout.write(self.style.SUCCESS(f"✓ {online_drivers.count()} drivers online"))
        else:
            self.stdout.write(self.style.ERROR("❌ No drivers online - DRIVERS MUST GO ONLINE!"))
        
        self.stdout.write("\n" + "=" * 70)
        if online_drivers.count() > 0:
            self.stdout.write(self.style.SUCCESS("✅ Driver assignment should work now!"))
        else:
            self.stdout.write(self.style.WARNING("⚠️  Drivers must log in and click 'Go Online'"))
        self.stdout.write("=" * 70)
