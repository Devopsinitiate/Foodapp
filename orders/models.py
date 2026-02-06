"""
Order management models for the food ordering application.
"""
from django.db import models
from django.core.validators import MinValueValidator
from users.models import User
from restaurants.models import Restaurant, MenuItem
import uuid


class Order(models.Model):
    """
    Main order model representing a customer's food order.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('cod', 'Cash on Delivery'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('online', 'Pay Now (Online)'),
        ('cod', 'Cash on Delivery'),
    ]

    DELIVERY_TYPE_CHOICES = [
        ('delivery', 'Delivery'),
        ('pickup', 'Pickup'),
    ]
    
    # Unique order identifier
    order_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )
    
    # Relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    
    # Order Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='online',
        help_text='Payment method chosen during checkout'
    )
    
    delivery_type = models.CharField(
        max_length=20,
        choices=DELIVERY_TYPE_CHOICES,
        default='delivery',
        help_text='Whether the order is for delivery or customer pickup'
    )
    
    # Delivery Information
    delivery_address = models.CharField(max_length=255, blank=True, null=True)
    delivery_city = models.CharField(max_length=100, blank=True, null=True)
    delivery_state = models.CharField(max_length=100, blank=True, null=True)
    delivery_postal_code = models.CharField(max_length=20, blank=True)
    delivery_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    delivery_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    delivery_instructions = models.TextField(
        blank=True,
        help_text='Special delivery instructions'
    )
    
    # Contact
    contact_phone = models.CharField(max_length=17)
    contact_email = models.EmailField()
    
    # Pricing
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    # Coupon
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    
    # Timestamps
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Notes
    special_requests = models.TextField(blank=True)
    cancellation_reason = models.TextField(
        blank=True,
        help_text='Reason for order cancellation'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['order_number']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.user.username}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_order_number():
        """Generate unique order number."""
        import random
        import string
        import time
        prefix = 'ORD'
        timestamp = str(int(time.time()))[-6:]
        random_str = ''.join(random.choices(string.digits, k=4))
        return f"{prefix}{timestamp}{random_str}"
    
    def calculate_total(self):
        """Calculate order total from items."""
        self.subtotal = sum(item.total_price for item in self.items.all())
        # Delivery fee is 0 for pickup orders
        actual_delivery_fee = Decimal('0.00') if self.delivery_type == 'pickup' else self.delivery_fee
        self.total = self.subtotal + actual_delivery_fee + self.tax - self.discount
        self.save(update_fields=['subtotal', 'total'])
    
    @property
    def full_delivery_address(self):
        """Returns formatted delivery address."""
        return f"{self.delivery_address}, {self.delivery_city}, {self.delivery_state} {self.delivery_postal_code}"
    
    @property
    def is_pending_payment(self):
        return self.payment_status == 'pending'
    
    @property
    def is_paid(self):
        return self.payment_status == 'paid'
    
    @property
    def has_review(self):
        """Check if order has been reviewed."""
        return self.reviews.exists()
    
    @property
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in ['pending', 'confirmed']
    
    def can_be_cancelled_by_customer(self):
        """Check if customer can cancel (within 5 minutes)."""
        from django.utils import timezone
        if not self.can_be_cancelled:
            return False
        time_elapsed = timezone.now() - self.created_at
        return time_elapsed.total_seconds() <= 300  # 5 minutes
    
    def mark_as_confirmed(self):
        """Mark order as confirmed."""
        from django.utils import timezone
        self.status = 'confirmed'
        self.confirmed_at = timezone.now()
        self.save(update_fields=['status', 'confirmed_at'])
    
    def mark_as_delivered(self):
        """Mark order as delivered."""
        from django.utils import timezone
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def get_payment_method_display(self):
        """Return human-readable payment method."""
        payment_method_map = dict(self.PAYMENT_METHOD_CHOICES)
        return payment_method_map.get(self.payment_method, self.payment_method)
    
    def get_payment_status_display(self):
        """Return human-readable payment status."""
        payment_status_map = dict(self.PAYMENT_STATUS_CHOICES)
        return payment_status_map.get(self.payment_status, self.payment_status)


class OrderItem(models.Model):
    """
    Individual items in an order.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    
    # Item details at time of order (for historical accuracy)
    item_name = models.CharField(max_length=200)
    item_description = models.TextField()
    price_at_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    # Quantity and customization
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    customizations = models.JSONField(
        default=dict,
        blank=True,
        help_text='Selected customizations (size, extras, etc.)'
    )
    special_instructions = models.TextField(blank=True)
    
    # Total for this item
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        return f"{self.quantity}x {self.item_name}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.price_at_order * self.quantity
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        """Recalculate total price."""
        self.total_price = self.price_at_order * self.quantity
        self.save(update_fields=['total_price'])


class Cart(models.Model):
    """
    Shopping cart for users (session-based for guests, DB-based for authenticated).
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='carts',
        null=True,
        blank=True
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text='For anonymous users'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.user:
            return f"Cart for {self.user.username}"
        return f"Cart (session: {self.session_key})"
    
    @property
    def total_items(self):
        """Total number of items in cart."""
        return sum(item.quantity for item in self.cart_items.all())
    
    @property
    def subtotal(self):
        """Calculate cart subtotal."""
        return sum(item.total_price for item in self.cart_items.all())
    
    def clear(self):
        """Remove all items from cart."""
        self.cart_items.all().delete()


class CartItem(models.Model):
    """
    Individual items in a shopping cart.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    customizations = models.JSONField(
        default=dict,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
        unique_together = ['cart', 'menu_item']
    
    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"
    
    @property
    def total_price(self):
        """Calculate total price for this cart item."""
        return self.menu_item.current_price * self.quantity


class Coupon(models.Model):
    """
    Discount coupons for orders - supports platform-wide and restaurant-specific.
    """
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    
    SCOPE_CHOICES = [
        ('platform', 'Platform-wide'),
        ('restaurant', 'Restaurant-specific'),
    ]
    
    # Basic Info
    code = models.CharField(
        max_length=50, 
        unique=True,
        db_index=True,
        help_text='Coupon code (case-insensitive)'
    )
    description = models.TextField(blank=True)
    
    # Discount Details
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Percentage (0-100) or fixed amount'
    )
    
    # Scope
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default='platform'
    )
    restaurant = models.ForeignKey(
        Restaurant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='specific_coupons',
        help_text='Leave blank for platform-wide coupons'
    )
    
    # Restrictions
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text='Minimum order amount required'
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Maximum discount cap (for percentage discounts)'
    )
    
    # Usage Limits
    max_total_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Total usage limit (leave blank for unlimited)'
    )
    max_uses_per_user = models.PositiveIntegerField(
        default=1,
        help_text='Times each user can use this coupon'
    )
    first_order_only = models.BooleanField(
        default=False,
        help_text='Only valid for first-time orders'
    )
    
    # Validity Period
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_coupons'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f"{self.code} ({self.get_discount_display()})"
    
    def get_discount_display(self):
        """Return human-readable discount."""
        if self.discount_type == 'percentage':
            return f"{self.discount_value}% off"
        return f"${self.discount_value} off"
    
    def is_valid_for_date(self):
        """Check if coupon is valid based on date."""
        from django.utils import timezone
        now = timezone.now()
        return self.valid_from <= now <= self.valid_until
    
    def get_usage_count(self):
        """Get total number of times coupon was used."""
        return self.usages.count()
    
    def calculate_discount(self, subtotal):
        """Calculate discount amount for given subtotal."""
        if self.discount_type == 'percentage':
            discount = (subtotal * self.discount_value) / 100
            # Apply max discount cap if set
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:  # fixed
            discount = self.discount_value
        
        # Don't exceed subtotal
        return min(discount, subtotal)


class CouponUsage(models.Model):
    """
    Track individual coupon usage for analytics and per-user limits.
    """
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usages'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='coupon_usages'
    )
    order = models.OneToOneField(
        'Order',
        on_delete=models.CASCADE,
        related_name='coupon_usage'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Actual discount amount applied'
    )
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['coupon', 'user']),
            models.Index(fields=['used_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} used {self.coupon.code} on order #{self.order.order_number}"