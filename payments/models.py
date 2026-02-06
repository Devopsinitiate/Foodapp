"""
Payment processing models for Paystack integration.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from users.models import User
from orders.models import Order
import uuid


class Payment(models.Model):
    """
    Payment transaction records.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('card', 'Credit/Debit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('ussd', 'USSD'),
        ('qr', 'QR Code'),
        ('mobile_money', 'Mobile Money'),
    ]
    
    # Unique payment reference
    reference = models.CharField(
        max_length=100,
        unique=True,
        editable=False
    )
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Payment details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    currency = models.CharField(
        max_length=3,
        default='NGN',
        help_text='Currency code (NGN, USD, etc.)'
    )
    
    # Status and method
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True
    )
    
    # Paystack integration fields
    paystack_reference = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )
    paystack_access_code = models.CharField(max_length=100, blank=True)
    authorization_url = models.URLField(blank=True)
    
    # Card details (last 4 digits only for security)
    card_type = models.CharField(max_length=20, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    card_bin = models.CharField(max_length=6, blank=True)
    bank = models.CharField(max_length=100, blank=True)
    
    # Transaction details
    paystack_transaction_id = models.CharField(max_length=100, blank=True)
    paystack_response = models.JSONField(
        default=dict,
        blank=True,
        help_text='Full Paystack response'
    )
    
    # Fees
    transaction_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Payment gateway fee'
    )
    
    # Additional info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional payment metadata'
    )
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['reference']),
            models.Index(fields=['paystack_reference']),
        ]
    
    def __str__(self):
        return f"Payment {self.reference} - {self.status}"
    
    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_reference():
        """Generate unique payment reference."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4().hex)[:8].upper()
        return f"PAY-{timestamp}-{unique_id}"
    
    @property
    def is_successful(self):
        return self.status == 'success'
    
    @property
    def can_be_refunded(self):
        return self.status == 'success' and not self.refunded_at
    
    def mark_as_success(self, paystack_data=None):
        """Mark payment as successful."""
        from django.db import transaction
        
        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Reload payment to get latest state
            payment = Payment.objects.select_for_update().get(pk=self.pk)
            
            # Update payment status
            payment.status = 'success'
            payment.paid_at = payment.paid_at or timezone.now()  # Keep original if already set
            
            if paystack_data:
                payment.paystack_response = paystack_data
                
                # Extract card details safely
                if 'authorization' in paystack_data:
                    auth = paystack_data['authorization']
                    payment.card_type = auth.get('card_type', '')
                    payment.card_last4 = auth.get('last4', '')
                    payment.card_bin = auth.get('bin', '')
                    payment.bank = auth.get('bank', '')
                
                # Extract transaction fee
                if 'fees' in paystack_data:
                    payment.transaction_fee = paystack_data['fees'] / 100  # Paystack returns in kobo
                
                # Extract payment method
                if 'channel' in paystack_data:
                    channel = paystack_data['channel']
                    if channel == 'card':
                        payment.payment_method = 'card'
                    elif channel == 'bank':
                        payment.payment_method = 'bank_transfer'
                    elif channel == 'ussd':
                        payment.payment_method = 'ussd'
                    elif channel == 'qr':
                        payment.payment_method = 'qr'
                    elif channel in ['mobile_money', 'mobile']:
                        payment.payment_method = 'mobile_money'
            
            payment.save(update_fields=[
                'status', 'paid_at', 'paystack_response',
                'card_type', 'card_last4', 'card_bin', 'bank', 'transaction_fee', 'payment_method'
            ])
            
            # ALWAYS update order payment status and method (idempotent)
            # This ensures order status is correct even if payment was already marked successful
            order = Order.objects.select_for_update().get(pk=payment.order_id)
            print(f'🔄 Updating order {order.order_number}: payment_status from {order.payment_status} to paid, payment_method from {order.payment_method} to {payment.payment_method or "online"}')
            order.payment_status = 'paid'
            # Only update payment method if not already set to 'cod' (Cash on Delivery)
            if order.payment_method != 'cod':
                order.payment_method = payment.payment_method or 'online'
            order.save(update_fields=['payment_status', 'payment_method'])
            print(f'✅ Order {order.order_number} updated: payment_status={order.payment_status}, payment_method={order.payment_method}')
            
            print(f"✅ Payment {payment.reference} marked as successful, Order {order.order_number} payment_status = paid, payment_method = {order.payment_method}")
            
            # Copy back to self for immediate access
            self.status = payment.status
            self.paid_at = payment.paid_at
            self.payment_method = payment.payment_method
            self.order.payment_status = 'paid'
            self.order.payment_method = order.payment_method
    
    def mark_as_failed(self, error_message=''):
        """Mark payment as failed."""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message'])
        
        # Update order payment status
        order = Order.objects.select_for_update().get(pk=self.order_id)
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status'])
    
    def initiate_refund(self, amount=None, reason=''):
        """Initiate refund process."""
        refund_amount = amount or self.amount
        refund = Refund.objects.create(
            payment=self,
            amount=refund_amount,
            reason=reason,
            initiated_by=self.user
        )
        return refund


class Refund(models.Model):
    """
    Refund transactions.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    reason = models.TextField()
    
    # Who initiated the refund
    initiated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_refunds'
    )
    
    # Paystack refund details
    paystack_refund_id = models.CharField(max_length=100, blank=True)
    paystack_response = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund for {self.payment.reference} - {self.amount}"
    
    def mark_as_completed(self):
        """Mark refund as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
        
        # Update original payment
        self.payment.status = 'refunded'
        self.payment.refunded_at = timezone.now()
        self.payment.save(update_fields=['status', 'refunded_at'])
        
        # Update order
        order = Order.objects.select_for_update().get(pk=self.payment.order_id)
        order.payment_status = 'refunded'
        order.save(update_fields=['payment_status'])


class PaymentWebhookLog(models.Model):
    """
    Log all webhook events from Paystack for debugging and auditing.
    """
    event = models.CharField(max_length=100)
    payload = models.JSONField()
    
    # Processing status
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    # Related payment (if found)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='webhook_logs'
    )
    
    # Request details
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    signature_valid = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', '-created_at']),
            models.Index(fields=['processed', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.event} at {self.created_at}"
    
    def mark_as_processed(self, error=None):
        """Mark webhook as processed."""
        self.processed = True
        self.processed_at = timezone.now()
        if error:
            self.processing_error = str(error)
        self.save(update_fields=['processed', 'processed_at', 'processing_error'])


class SavedCard(models.Model):
    """
    Saved payment methods for users (tokenized cards).
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='saved_cards'
    )
    
    # Paystack authorization
    authorization_code = models.CharField(max_length=100, unique=True)
    
    # Card details (safe to store)
    card_type = models.CharField(max_length=20)
    card_last4 = models.CharField(max_length=4)
    card_bin = models.CharField(max_length=6)
    bank = models.CharField(max_length=100)
    brand = models.CharField(max_length=50, blank=True)
    
    # Expiry
    exp_month = models.CharField(max_length=2)
    exp_year = models.CharField(max_length=4)
    
    # Status
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Metadata
    customer_code = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-is_default', '-last_used']
        unique_together = ['user', 'authorization_code']
    
    def __str__(self):
        return f"{self.card_type} ending in {self.card_last4}"
    
    def save(self, *args, **kwargs):
        # If this card is set as default, remove default from other cards
        if self.is_default:
            SavedCard.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Check if card is expired."""
        from datetime import datetime
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        exp_year_int = int(self.exp_year)
        exp_month_int = int(self.exp_month)
        
        if exp_year_int < current_year:
            return True
        if exp_year_int == current_year and exp_month_int < current_month:
            return True
        return False
    
    def mark_as_used(self):
        """Update last used timestamp."""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used'])