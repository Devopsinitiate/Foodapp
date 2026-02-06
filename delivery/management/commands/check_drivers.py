"""Management command to diagnose driver availability issues"""
from django.core.management.base import BaseCommand
from users.models import User
from delivery.models import DriverAvailability, Delivery
from orders.models import Order
from restaurants.models import Restaurant


class Command(BaseCommand):
    help = 'Diagnose driver availability issues'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("DRIVER AVAILABILITY DIAGNOSTIC")
        self.stdout.write("=" * 60)

        # Check verified drivers
        self.stdout.write("\n1. VERIFIED DRIVERS:")
        drivers = User.objects.filter(is_driver=True, is_verified_driver=True, is_active=True)
        self.stdout.write(f"   Total: {drivers.count()}")
        for d in drivers:
            self.stdout.write(f"   - {d.email}: verified={d.is_verified_driver}, active={d.is_active}")

        # Check DriverAvailability records
        self.stdout.write("\n2. DRIVER AVAILABILITY RECORDS:")
        avail_records = DriverAvailability.objects.select_related('driver').all()
        self.stdout.write(f"   Total: {avail_records.count()}")
        
        if avail_records.count() == 0:
            self.stdout.write(self.style.ERROR("   ⚠️  NO DriverAvailability RECORDS FOUND!"))
            self.stdout.write("   This is the problem! Drivers need DriverAvailability records.")
        
        for a in avail_records:
            self.stdout.write(f"\n   - Driver: {a.driver.email}")
            self.stdout.write(f"     Online: {a.is_online}, Available: {a.is_available}")
            self.stdout.write(f"     Verified: {a.driver.is_verified_driver}, Active: {a.driver.is_active}")
            self.stdout.write(f"     Location: lat={a.current_latitude}, lon={a.current_longitude}")

        # Check order 32
        self.stdout.write("\n3. RECENT ORDER DETAILS:")
        try:
            order = Order.objects.select_related('restaurant').filter(id__gte=30).order_by('-id').first()
            if order:
                self.stdout.write(f"   Order: {order.order_number} (ID: {order.id})")
                self.stdout.write(f"   Restaurant: {order.restaurant.name}")
                self.stdout.write(f"   Restaurant coordinates: lat={order.restaurant.latitude}, lon={order.restaurant.longitude}")
                
                # Check if coordinates are set
                if not order.restaurant.latitude or not order.restaurant.longitude:
                    self.stdout.write(self.style.ERROR("   ⚠️  WARNING: Restaurant has no coordinates!"))
            else:
                self.stdout.write("   No recent orders found")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error: {e}"))

        # Test driver search
        self.stdout.write("\n4. TESTING DRIVER SEARCH:")
        try:
            order = Order.objects.select_related('restaurant').filter(id__gte=30).order_by('-id').first()
            if order and order.restaurant.latitude and order.restaurant.longitude:
                from delivery.assignment import find_available_drivers
                drivers_found = find_available_drivers(
                    order.restaurant.latitude,
                    order.restaurant.longitude,
                    radius_km=10
                )
                self.stdout.write(f"   Drivers found: {len(drivers_found)}")
                if len(drivers_found) == 0:
                    self.stdout.write(self.style.ERROR("   ⚠️  NO DRIVERS FOUND!"))
                for d in drivers_found:
                    self.stdout.write(f"   - {d['driver'].email}: distance={d['distance']:.2f}km")
            else:
                self.stdout.write(self.style.ERROR("   Cannot search: No order or restaurant coordinates"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error: {e}"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("\nDiagnostic complete!"))
