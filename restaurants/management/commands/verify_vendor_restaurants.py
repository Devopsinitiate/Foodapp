"""
Management command to verify restaurants from approved vendors.
Auto-verifies all restaurants owned by active vendors.
"""
from django.core.management.base import BaseCommand
from restaurants.models import Restaurant


class Command(BaseCommand):
    help = 'Verify all restaurants owned by approved vendors'

    def handle(self, *args, **options):
        self.stdout.write('Checking restaurants...')
        
        verified_count = 0
        
        # Get all restaurants from active vendors
        restaurants = Restaurant.objects.select_related('owner').filter(
            owner__user_type='vendor',
            owner__is_active_vendor=True,
            is_verified=False
        )
        
        for restaurant in restaurants:
            restaurant.is_verified = True
            restaurant.save(update_fields=['is_verified'])
            verified_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ Verified: {restaurant.name} (Owner: {restaurant.owner.username})'
                )
            )
        
        if verified_count == 0:
            self.stdout.write(
                self.style.SUCCESS('All restaurants from approved vendors are already verified!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully verified {verified_count} restaurant(s)!'
                )
            )
