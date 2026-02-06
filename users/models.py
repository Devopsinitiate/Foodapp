"""
User models for the food ordering application.
Extends Django's AbstractUser to add custom fields.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class User(AbstractUser):
    """
    Custom user model with additional fields for customers, vendors, and drivers.
    """
    USER_TYPES = [
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('driver', 'Driver'),
        ('admin', 'Admin'),
    ]
    
    user_type = models.CharField(
        max_length=10,
        choices=USER_TYPES,
        default='customer',
        help_text='Type of user account'
    )
    
    # Contact Information
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text='Contact phone number'
    )
    
    # Address Information
    street_address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Optional location coordinates (for delivery optimization)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Latitude coordinate'
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='Longitude coordinate'
    )
    
    # Profile
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True
    )
    bio = models.TextField(max_length=500, blank=True)
    
    # Favorites
    favorite_restaurants = models.ManyToManyField(
        'restaurants.Restaurant',
        related_name='favorited_by',
        blank=True,
        help_text='User\'s favorite restaurants'
    )
    
    # Account Status
    is_verified = models.BooleanField(
        default=False,
        help_text='Email/phone verification status'
    )
    is_active_vendor = models.BooleanField(
        default=False,
        help_text='Whether vendor account is approved and active'
    )
    is_available_driver = models.BooleanField(
        default=False,
        help_text='Whether driver is currently available for deliveries'
    )
    
    # Driver Verification Fields
    driver_license_number = models.CharField(
        max_length=50,
        blank=True,
        help_text='Driver license number'
    )
    driver_license_expiry = models.DateField(
        null=True,
        blank=True,
        help_text='Driver license expiration date'
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=[
            ('bike', 'Motorcycle'),
            ('bicycle', 'Bicycle'),
            ('car', 'Car'),
            ('scooter', 'Scooter'),
        ],
        blank=True,
        help_text='Type of vehicle for deliveries'
    )
    vehicle_plate = models.CharField(
        max_length=20,
        blank=True,
        help_text='Vehicle license plate number'
    )
    vehicle_insurance_expiry = models.DateField(
        null=True,
        blank=True,
        help_text='Vehicle insurance expiration date'
    )
    is_verified_driver = models.BooleanField(
        default=False,
        help_text='Whether driver has been verified and approved'
    )
    driver_documents_uploaded = models.BooleanField(
        default=False,
        help_text='Whether driver has uploaded required documents'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_type', 'is_active']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
    
    @property
    def full_address(self):
        """Returns formatted full address."""
        parts = [
            self.street_address,
            self.city,
            self.state,
            self.postal_code
        ]
        return ', '.join(filter(None, parts))
    
    @property
    def is_customer(self):
        return self.user_type == 'customer'
    
    @property
    def is_vendor(self):
        return self.user_type == 'vendor'
    
    @property
    def is_driver(self):
        return self.user_type == 'driver'
    
    def get_coordinates(self):
        """Returns tuple of (latitude, longitude) if available."""
        if self.latitude and self.longitude:
            return (float(self.latitude), float(self.longitude))
        return None


class UserProfile(models.Model):
    """
    Extended profile information for users.
    Separate from User model to keep it lightweight.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Preferences
    favorite_cuisines = models.JSONField(
        default=list,
        blank=True,
        help_text='List of favorite cuisine types'
    )
    dietary_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text='Dietary restrictions (vegetarian, vegan, etc.)'
    )
    
    # Notifications
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    
    # Statistics (for gamification/loyalty)
    total_orders = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00
    )
    loyalty_points = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    def add_loyalty_points(self, points):
        """Add loyalty points to user's account."""
        self.loyalty_points += points
        self.save(update_fields=['loyalty_points'])
    
    def increment_order_stats(self, order_total):
        """Update order statistics."""
        self.total_orders += 1
        self.total_spent += order_total
        self.save(update_fields=['total_orders', 'total_spent'])