from django.core.management.base import BaseCommand
from orders.models import Order
from payments.models import Payment


class Command(BaseCommand):
    help = 'Fix payment status and method synchronization between Payment and Order models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find orders with successful payments but incorrect payment_status
        successful_payments = Payment.objects.filter(status='success').select_related('order')
        
        fixed_orders = 0
        fixed_methods = 0
        
        for payment in successful_payments:
            order = payment.order
            
            # Fix payment status if incorrect
            if order.payment_status != 'paid':
                self.stdout.write(
                    f"Fixing payment status for order {order.order_number}: "
                    f"{order.payment_status} -> paid"
                )
                
                if not dry_run:
                    order.payment_status = 'paid'
                    order.save(update_fields=['payment_status'])
                    fixed_orders += 1
            
            # Fix payment method if incorrect
            if payment.payment_method and order.payment_method != payment.payment_method:
                self.stdout.write(
                    f"Fixing payment method for order {order.order_number}: "
                    f"{order.payment_method} -> {payment.payment_method}"
                )
                
                if not dry_run:
                    order.payment_method = payment.payment_method
                    order.save(update_fields=['payment_method'])
                    fixed_methods += 1
        
        # Also fix orders that are marked as 'cod' but have no payment record
        cod_orders = Order.objects.filter(payment_method='cod', payment_status='pending')
        for order in cod_orders:
            self.stdout.write(
                f"Fixing COD order {order.order_number}: payment_status {order.payment_status} -> cod"
            )
            
            if not dry_run:
                order.payment_status = 'cod'
                order.save(update_fields=['payment_status'])
                fixed_orders += 1
        
        # Find orders with failed payments but incorrect payment_status
        failed_payments = Payment.objects.filter(status='failed').select_related('order')
        for payment in failed_payments:
            order = payment.order
            
            if order.payment_status != 'failed':
                self.stdout.write(
                    f"Fixing failed payment status for order {order.order_number}: "
                    f"{order.payment_status} -> failed"
                )
                
                if not dry_run:
                    order.payment_status = 'failed'
                    order.save(update_fields=['payment_status'])
                    fixed_orders += 1
        
        # Find orders with refunded payments but incorrect payment_status
        refunded_payments = Payment.objects.filter(status='refunded').select_related('order')
        for payment in refunded_payments:
            order = payment.order
            
            if order.payment_status != 'refunded':
                self.stdout.write(
                    f"Fixing refunded payment status for order {order.order_number}: "
                    f"{order.payment_status} -> refunded"
                )
                
                if not dry_run:
                    order.payment_status = 'refunded'
                    order.save(update_fields=['payment_status'])
                    fixed_orders += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would fix {fixed_orders} orders and {fixed_methods} payment methods"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully fixed {fixed_orders} orders and {fixed_methods} payment methods"
                )
            )