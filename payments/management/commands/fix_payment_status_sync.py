"""
Management command to fix payment status synchronization issues between Payment and Order models.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from payments.models import Payment
from orders.models import Order


class Command(BaseCommand):
    help = 'Fix payment status synchronization between Payment and Order models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of records to process',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write(
            self.style.WARNING(
                f'Starting payment status synchronization fix (dry_run={dry_run}, limit={limit})'
            )
        )

        # Find payments that are successful but orders don't reflect this
        successful_payments = Payment.objects.filter(status='success')

        if limit:
            successful_payments = successful_payments[:limit]

        fixed_count = 0
        issues_found = 0

        for payment in successful_payments:
            order = payment.order
            
            # Check if order payment status is not aligned with payment status
            needs_update = False
            update_fields = []

            if payment.status == 'success' and order.payment_status != 'paid':
                issues_found += 1
                self.stdout.write(
                    f'  Issue found: Payment {payment.reference} is successful but Order {order.order_number} has payment_status={order.payment_status}'
                )
                
                if not dry_run:
                    needs_update = True
                    order.payment_status = 'paid'
                    update_fields.append('payment_status')
                    
                    # Also update payment method if not COD
                    if order.payment_method != 'cod' and payment.payment_method:
                        order.payment_method = payment.payment_method
                        update_fields.append('payment_method')

            if needs_update:
                with transaction.atomic():
                    order.save(update_fields=update_fields)
                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'    Fixed: Order {order.order_number} payment_status updated to {order.payment_status}'
                        )
                    )

        # Also check for orders that have payment_status='paid' but no successful payment
        paid_orders = Order.objects.filter(payment_status='paid')
        
        if limit:
            paid_orders = paid_orders[:limit]

        for order in paid_orders:
            # Check if there's a successful payment for this order
            successful_payment_exists = order.payments.filter(status='success').exists()
            
            if not successful_payment_exists:
                issues_found += 1
                self.stdout.write(
                    f'  Issue found: Order {order.order_number} has payment_status=Paid but no successful payment record'
                )
                
                # Check if there's any successful payment for this order in any other way
                # This might be an orphaned record
                if not dry_run:
                    # We can't fix this without knowing the real status, so we'll just log it
                    # In a real scenario, you might want to investigate these manually
                    pass
        
        # Check for orders that should be 'paid' based on successful payments but aren't
        orders_with_successful_payments = Order.objects.filter(
            payments__status='success'
        ).distinct()
        
        if limit:
            orders_with_successful_payments = orders_with_successful_payments[:limit]
        
        for order in orders_with_successful_payments:
            if order.payment_status != 'paid':
                issues_found += 1
                self.stdout.write(
                    f'  Issue found: Order {order.order_number} has successful payment but payment_status={order.payment_status}'
                )
                
                if not dry_run:
                    order.payment_status = 'paid'
                    # Get the payment method from the successful payment
                    successful_payment = order.payments.filter(status='success').first()
                    if order.payment_method != 'cod' and successful_payment and successful_payment.payment_method:
                        order.payment_method = successful_payment.payment_method
                    order.save(update_fields=['payment_status', 'payment_method'])
                    fixed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'    Fixed: Order {order.order_number} payment_status updated to {order.payment_status}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'Completed payment status synchronization fix:\n'
                f'  Issues found: {issues_found}\n'
                f'  Records fixed: {fixed_count}\n'
                f'  Dry run: {dry_run}'
            )
        )