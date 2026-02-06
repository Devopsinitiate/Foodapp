"""
Restaurant and menu models for the food ordering application.
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from users.models import User


class Category(models.Model):
    """
    Food categories (e.g., Pizza, Burgers, Asian, Desserts).
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text='Icon class or emoji'
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(
        default=0,
        help_text='Display order (lower numbers first)'
    )
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Restaurant(models.Model):
    """
    Restaurant/Vendor information.
    """
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='restaurants',
        limit_choices_to={'user_type': 'vendor'}
    )
    
    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    logo = models.ImageField(
        upload_to='restaurants/logos/',
        null=True,
        blank=True
    )
    cover_image = models.ImageField(
        upload_to='restaurants/covers/',
        null=True,
        blank=True
    )
    
    # Contact & Location
    phone_number = models.CharField(max_length=17)
    email = models.EmailField()
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    
    # Categories & Cuisine
    categories = models.ManyToManyField(
        Category,
        related_name='restaurants',
        help_text='Food categories offered'
    )
    cuisine_type = models.CharField(
        max_length=100,
        help_text='e.g., Italian, Chinese, Nigerian'
    )
    
    # Business Hours (stored as JSON)
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text='Operating hours by day of week'
    )
    
    # Ratings & Reviews
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0), MaxValueValidator(5)]
    )
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Delivery Settings
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    minimum_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)]
    )
    estimated_delivery_time = models.PositiveIntegerField(
        default=30,
        help_text='Estimated delivery time in minutes'
    )
    delivery_radius = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        help_text='Delivery radius in kilometers'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_accepting_orders = models.BooleanField(default=True)
    is_verified = models.BooleanField(
        default=False,
        help_text='Admin verification status'
    )
    
    # Statistics
    total_orders = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-average_rating', 'name']
        indexes = [
            models.Index(fields=['is_active', 'is_accepting_orders']),
            models.Index(fields=['average_rating']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def full_address(self):
        """Returns formatted address."""
        return f"{self.street_address}, {self.city}, {self.state} {self.postal_code}"
    
    def update_rating(self):
        """Recalculate average rating from reviews."""
        from django.db.models import Avg
        result = self.reviews.aggregate(avg=Avg('rating'))
        self.average_rating = result['avg'] or 0.00
        self.total_reviews = self.reviews.count()
        self.save(update_fields=['average_rating', 'total_reviews'])


class MenuItem(models.Model):
    """
    Individual menu items offered by restaurants.
    """
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='menu_items'
    )
    
    # Basic Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    description = models.TextField()
    image = models.ImageField(
        upload_to='menu_items/',
        null=True,
        blank=True
    )
    
    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    discounted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    
    # Details
    preparation_time = models.PositiveIntegerField(
        default=15,
        help_text='Preparation time in minutes'
    )
    calories = models.PositiveIntegerField(null=True, blank=True)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    spice_level = models.CharField(
        max_length=20,
        choices=[
            ('none', 'Not Spicy'),
            ('mild', 'Mild'),
            ('medium', 'Medium'),
            ('hot', 'Hot'),
            ('extra_hot', 'Extra Hot'),
        ],
        default='none'
    )
    
    # Availability
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    stock_quantity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Leave blank for unlimited stock'
    )
    
    # Customization options (stored as JSON)
    customization_options = models.JSONField(
        default=list,
        blank=True,
        help_text='Available customizations (size, extras, etc.)'
    )
    
    # Statistics
    total_orders = models.PositiveIntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_featured', 'name']
        indexes = [
            models.Index(fields=['restaurant', 'is_available']),
            models.Index(fields=['category', 'is_available']),
        ]
        unique_together = ['restaurant', 'slug']
    
    def __str__(self):
        return f"{self.name} - {self.restaurant.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    @property
    def current_price(self):
        """Returns the current price (discounted if available)."""
        return self.discounted_price if self.discounted_price else self.price
    
    @property
    def is_on_sale(self):
        """Check if item has a discount."""
        return self.discounted_price is not None and self.discounted_price < self.price
    
    def is_in_stock(self):
        """Check if item is in stock."""
        if self.stock_quantity is None:
            return True
        return self.stock_quantity > 0
    
    def decrease_stock(self, quantity=1):
        """Decrease stock quantity."""
        if self.stock_quantity is not None:
            self.stock_quantity = max(0, self.stock_quantity - quantity)
            self.save(update_fields=['stock_quantity'])


class Review(models.Model):
    """
    Customer reviews for restaurants.
    """
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    
    # Optional order reference
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews'
    )
    
    # Vendor response
    vendor_response = models.TextField(blank=True, null=True)
    vendor_response_date = models.DateTimeField(blank=True, null=True)
    
    # Additional features
    helpful_count = models.PositiveIntegerField(default=0)
    is_verified_purchase = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=True)  # For moderation
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['restaurant', 'user', 'order']
    
    def __str__(self):
        return f"{self.user.username} - {self.restaurant.name} ({self.rating}⭐)"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update restaurant rating
        self.restaurant.update_rating()

