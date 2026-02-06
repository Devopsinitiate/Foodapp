"""
Management command to fix payment status discrepancies.
This command syncs payment status between Payment and Order models.

Usage:
    python manage.py fix_payment_status
    python manage.py fix_payment_status --dry-run  # Preview without making changes
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from payments.models import Payment
from orders.models import Order


class Command(BaseCommand):
    help = 'Fix payment status discrepancies between Payment and Order models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('Analyzing payment status...\n')
        
        # Find orders with paid payments but pending payment_status
        orders_to_fix = []
        
        # Get all successful payments
        successful_payments = Payment.objects.filter(status='success').select_related('order')
        
        fixed_count = 0
        already_correct = 0
        
        for payment in successful_payments:
            order = payment.order
            
            if order.payment_status != 'paid':
                orders_to_fix.append({
                    'order': order,
                    'payment': payment,
                    'current_status': order.payment_status,
                })
                
                self.stdout.write(
                    self.style.WARNING(
                        f'❌ Order #{order.order_number}: '
                        f'Payment is SUCCESS but order payment_status is {order.payment_status}'
                    )
                )
                
                if not dry_run:
                    order.payment_status = 'paid'
                    order.save(update_fields=['payment_status'])
                    
                    # Also ensure payment method is set
                    if not payment.payment_method and payment.card_type:
                        payment.payment_method = 'card'
                        payment.save(update_fields=['payment_method'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ Fixed: Set order payment_status to "paid"'
                        )
                    )
                    fixed_count += 1
                else:
                    self.stdout.write(
                        self.style.NOTICE(
                            f'  🔧 Would fix: Set order payment_status to "paid"'
                        )
                    )
            else:
                already_correct += 1
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'✅ Already correct: {already_correct}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'🔧 Would fix: {len(orders_to_fix)}'))
            if orders_to_fix:
                self.stdout.write('\nRun without --dry-run to apply fixes')
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Fixed: {fixed_count}'))
        
        self.stdout.write('='*60)
        
        # Check for opposite issue: paid orders without successful payments
        self.stdout.write('\n🔍 Checking for paid orders without successful payments...')
        
        paid_orders = Order.objects.filter(payment_status='paid')
        orphaned_count = 0
        
        for order in paid_orders:
            successful_payment = Payment.objects.filter(
                order=order,
                status='success'
            ).first()
            
            if not successful_payment:
                self.stdout.write(
                    self.style.ERROR(
                        f'⚠️ Order #{order.order_number} is marked as "paid" '
                        f'but has no successful payment record!'
                    )
                )
                orphaned_count += 1
        
        if orphaned_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'\n⚠️ Found {orphaned_count} orders marked as paid without successful payment records.'
                )
            )
            self.stdout.write(
                self.style.NOTICE(
                    'These may need manual review. Check if payments exist with different status.'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ No orphaned paid orders found'))
        
        self.stdout.write('\n✨ Payment status check complete!')
