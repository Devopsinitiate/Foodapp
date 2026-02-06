"""
Delivery management models for tracking orders and drivers.
"""
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from users.models import User
from orders.models import Order


class Delivery(models.Model):
    """
    Delivery tracking for orders.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Assignment'),
        ('assigned', 'Assigned to Driver'),
        ('accepted', 'Accepted by Driver'),
        ('picked_up', 'Picked Up'),
        ('en_route', 'En Route to Customer'),
        ('arrived', 'Arrived at Location'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed Delivery'),
    ]
    
    # Relationships
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery'
    )
    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deliveries',
        limit_choices_to={'user_type': 'driver'}
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Location tracking
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Driver current latitude'
    )
    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Driver current longitude'
    )
    
    # Pickup location (restaurant)
    pickup_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    pickup_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Delivery location (customer)
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
    
    # Time tracking
    estimated_pickup_time = models.DateTimeField(null=True, blank=True)
    actual_pickup_time = models.DateTimeField(null=True, blank=True)
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    
    # Distance and duration
    distance_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text='Distance in kilometers'
    )
    estimated_duration_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Estimated delivery time in minutes'
    )
    
    # Delivery details
    delivery_instructions = models.TextField(blank=True)
    delivery_photo = models.ImageField(
        upload_to='deliveries/proof/',
        null=True,
        blank=True,
        help_text='Proof of delivery photo'
    )
    signature = models.TextField(
        blank=True,
        help_text='Customer signature (base64)'
    )
    
    # Driver notes
    driver_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    
    # Rating
    rating = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Customer rating (1-5)'
    )
    feedback = models.TextField(blank=True)
    
    # Timestamps
    assigned_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Deliveries'
        indexes = [
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Delivery for Order {self.order.order_number}"
    
    @property
    def is_active(self):
        """Check if delivery is currently active."""
        return self.status in ['assigned', 'accepted', 'picked_up', 'en_route']
    
    @property
    def is_completed(self):
        """Check if delivery is completed."""
        return self.status == 'delivered'
    
    def assign_to_driver(self, driver):
        """Assign delivery to a driver."""
        self.driver = driver
        self.status = 'assigned'
        self.assigned_at = timezone.now()
        self.save(update_fields=['driver', 'status', 'assigned_at'])
    
    def accept_delivery(self):
        """Driver accepts the delivery."""
        self.status = 'accepted'
        self.accepted_at = timezone.now()
        self.save(update_fields=['status', 'accepted_at'])
        
        # Mark driver as busy when they accept
        if self.driver:
            try:
                from delivery.models import DriverAvailability
                availability = DriverAvailability.objects.get(driver=self.driver)
                availability.is_available = False
                availability.save(update_fields=['is_available'])
            except DriverAvailability.DoesNotExist:
                pass  # Driver availability not set up yet
    
    def mark_picked_up(self):
        """Mark order as picked up from restaurant."""
        self.status = 'picked_up'
        self.actual_pickup_time = timezone.now()
        self.save(update_fields=['status', 'actual_pickup_time'])
        
        # Send notifications (Non-blocking)
        try:
            from utils.emails import send_out_for_delivery_email, send_email_async
            send_email_async(send_out_for_delivery_email, self.order, self)
        except Exception as e:
            print(f"Failed to trigger email: {e}")
            
        from core.utils.websocket_notifications import notify_customer_order_status, notify_vendor_order_update
        notify_customer_order_status(
            self.order, 
            'picked_up', 
            'Your order has been picked up and is on the way to you!'
        )
        notify_vendor_order_update(
            self.order, 
            f'Order #{self.order.order_number} has been picked up by driver.'
        )
    
    def mark_en_route(self):
        """Mark delivery as en route to customer."""
        self.status = 'en_route'
        self.save(update_fields=['status'])
        
        # Send notifications (Non-blocking)
        from core.utils.websocket_notifications import notify_customer_order_status, notify_vendor_order_update
        notify_customer_order_status(
            self.order, 
            'en_route', 
            'Your order is on the way! Driver is heading to your location.'
        )
        notify_vendor_order_update(
            self.order, 
            f'Order #{self.order.order_number} is on the way to customer.'
        )
    
    def mark_delivered(self):
        """Mark delivery as completed."""
        self.status = 'delivered'
        self.actual_delivery_time = timezone.now()
        self.save(update_fields=['status', 'actual_delivery_time'])
        
        # Update order status
        self.order.mark_as_delivered()
        
        # Send order delivered email (Non-blocking)
        try:
            from utils.emails import send_order_delivered_email, send_email_async
            send_email_async(send_order_delivered_email, self.order)
        except Exception as e:
            print(f"Failed to trigger email: {e}")
            
        # Send notifications (Non-blocking)
        from core.utils.websocket_notifications import notify_customer_order_status, notify_vendor_order_update
        notify_customer_order_status(
            self.order, 
            'delivered', 
            'Your order has been delivered! Enjoy your meal!'
        )
        notify_vendor_order_update(
            self.order, 
            f'Order #{self.order.order_number} has been delivered to customer.'
        )
        
        # Restore driver availability if they're still online
        if self.driver:
            try:
                availability = self.driver.availability
                if availability.is_online:
                    availability.is_available = True
                    availability.save(update_fields=['is_available'])
                # Update delivery statistics
                availability.increment_deliveries(successful=True)
            except Exception as e:
                # Log but don't fail if availability update fails
                print(f"Error updating driver availability: {e}")
    
    def update_location(self, latitude, longitude):
        """Update driver's current location."""
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.updated_at = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'updated_at'])
    
    def calculate_eta(self):
        """Calculate estimated time of arrival (placeholder - integrate with maps API)."""
        if self.distance_km and self.status == 'en_route':
            # Simple calculation: assume 30 km/h average speed
            minutes = (float(self.distance_km) / 30) * 60
            return timezone.now() + timezone.timedelta(minutes=minutes)
        return None


class DeliveryLocation(models.Model):
    """
    Track delivery location history for real-time tracking.
    """
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name='location_history'
    )
    
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Additional tracking info
    speed = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Speed in km/h'
    )
    heading = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Direction in degrees (0-360)'
    )
    accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Location accuracy in meters'
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['delivery', '-timestamp']),
        ]
    
    def __str__(self):
        return f"Location at {self.timestamp}"


class DriverAvailability(models.Model):
    """
    Track driver availability and working hours.
    """
    driver = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='availability',
        limit_choices_to={'user_type': 'driver'}
    )
    
    is_available = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    
    # Current location
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Statistics
    total_deliveries = models.PositiveIntegerField(default=0)
    successful_deliveries = models.PositiveIntegerField(default=0)
    cancelled_deliveries = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )
    
    # Vehicle information
    vehicle_type = models.CharField(
        max_length=50,
        choices=[
            ('bike', 'Motorcycle'),
            ('bicycle', 'Bicycle'),
            ('car', 'Car'),
            ('scooter', 'Scooter'),
        ],
        default='bike'
    )
    vehicle_plate = models.CharField(max_length=20, blank=True)
    
    # Session tracking
    last_online = models.DateTimeField(null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Driver Availabilities'
    
    def __str__(self):
        return f"{self.driver.username} - {'Available' if self.is_available else 'Unavailable'}"
    
    @property
    def success_rate(self):
        """Calculate delivery success rate."""
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100
    
    def go_online(self):
        """Set driver status to online."""
        self.is_online = True
        self.is_available = True
        self.last_online = timezone.now()
        self.save(update_fields=['is_online', 'is_available', 'last_online'])
    
    def go_offline(self):
        """Set driver status to offline."""
        self.is_online = False
        self.is_available = False
        self.save(update_fields=['is_online', 'is_available'])
    
    def update_location(self, latitude, longitude):
        """Update driver's current location."""
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_location_update = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'last_location_update'])
    
    def increment_deliveries(self, successful=True):
        """Update delivery statistics."""
        self.total_deliveries += 1
        if successful:
            self.successful_deliveries += 1
        else:
            self.cancelled_deliveries += 1
        self.save(update_fields=['total_deliveries', 'successful_deliveries', 'cancelled_deliveries'])


class DeliveryZone(models.Model):
    """
    Define delivery zones and their settings.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Geographic boundaries (simplified - use PostGIS for production)
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Zone radius in kilometers'
    )
    
    # Pricing
    base_delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    per_km_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Operating hours (JSON format)
    operating_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text='Operating hours by day of week'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def is_location_in_zone(self, latitude, longitude):
        """Check if a location is within this delivery zone."""
        from math import radians, sin, cos, sqrt, atan2
        
        # Haversine formula to calculate distance
        R = 6371  # Earth's radius in km
        
        lat1 = radians(float(self.center_latitude))
        lon1 = radians(float(self.center_longitude))
        lat2 = radians(float(latitude))
        lon2 = radians(float(longitude))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return distance <= float(self.radius_km)
    
    def calculate_delivery_fee(self, distance_km):
        """Calculate delivery fee based on distance."""
        return float(self.base_delivery_fee) + (float(distance_km) * float(self.per_km_rate))