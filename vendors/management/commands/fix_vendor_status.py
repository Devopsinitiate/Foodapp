"""
Management command to fix vendor user status.
Syncs VendorProfile application_status with User is_active_vendor and user_type.
"""
from django.core.management.base import BaseCommand
from vendors.models import VendorProfile


class Command(BaseCommand):
    help = 'Fix vendor user status to match their VendorProfile application status'

    def handle(self, *args, **options):
        self.stdout.write('Checking vendor profiles...')
        
        fixed_count = 0
        
        # Get all vendor profiles
        vendor_profiles = VendorProfile.objects.select_related('user').all()
        
        for profile in vendor_profiles:
            user = profile.user
            needs_update = False
            updates = {}
            
            # Check if status matches
            if profile.application_status == 'approved':
                if not user.is_active_vendor:
                    updates['is_active_vendor'] = True
                    needs_update = True
                    self.stdout.write(
                        self.style.WARNING(
                            f'  - {user.username}: Setting is_active_vendor = True'
                        )
                    )
                
                if user.user_type != 'vendor':
                    updates['user_type'] = 'vendor'
                    needs_update = True
                    self.stdout.write(
                        self.style.WARNING(
                            f'  - {user.username}: Setting user_type = vendor'
                        )
                    )
            else:
                # Not approved, should not be active vendor
                if user.is_active_vendor:
                    updates['is_active_vendor'] = False
                    needs_update = True
                    self.stdout.write(
                        self.style.WARNING(
                            f'  - {user.username}: Setting is_active_vendor = False (status: {profile.application_status})'
                        )
                    )
            
            # Apply updates if needed
            if needs_update:
                for field, value in updates.items():
                    setattr(user, field, value)
                user.save(update_fields=list(updates.keys()))
                fixed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Fixed {user.username}'
                    )
                )
        
        if fixed_count == 0:
            self.stdout.write(
                self.style.SUCCESS('All vendor statuses are correct! No fixes needed.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully fixed {fixed_count} vendor(s)!'
                )
            )
