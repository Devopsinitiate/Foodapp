"""
Django Admin configuration for Restaurants app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Restaurant, MenuItem, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for Category model."""
    
    list_display = ['name', 'slug', 'icon', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['order', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        ('Status', {
            'fields': ('is_active', 'order')
        }),
    )


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    """Admin for Restaurant model."""
    
    list_display = [
        'name', 'owner_name', 'cuisine_type', 'average_rating_display',
        'is_active', 'is_accepting_orders', 'is_verified', 'created_at'
    ]
    list_filter = [
        'is_active', 'is_accepting_orders', 'is_verified',
        'cuisine_type', 'created_at'
    ]
    search_fields = ['name', 'owner__username', 'email', 'phone_number']
    readonly_fields = [
        'slug', 'average_rating', 'total_reviews', 'total_orders',
        'created_at', 'updated_at'
    ]
    filter_horizontal = ['categories']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('owner', 'name', 'slug', 'description')
        }),
        ('Images', {
            'fields': ('logo', 'cover_image')
        }),
        ('Contact & Location', {
            'fields': (
                'phone_number', 'email', 'street_address',
                'city', 'state', 'postal_code',
                'latitude', 'longitude'
            )
        }),
        ('Categories & Cuisine', {
            'fields': ('categories', 'cuisine_type')
        }),
        ('Business Hours', {
            'fields': ('business_hours',)
        }),
        ('Ratings & Reviews', {
            'fields': ('average_rating', 'total_reviews'),
            'classes': ('collapse',)
        }),
        ('Delivery Settings', {
            'fields': (
                'delivery_fee', 'minimum_order',
                'estimated_delivery_time', 'delivery_radius'
            )
        }),
        ('Status', {
            'fields': (
                'is_active', 'is_accepting_orders', 'is_verified'
            )
        }),
        ('Statistics', {
            'fields': ('total_orders',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def owner_name(self, obj):
        """Display owner name."""
        return obj.owner.get_full_name() or obj.owner.username
    owner_name.short_description = 'Owner'
    
    def average_rating_display(self, obj):
        """Display average rating with stars."""
        stars = '⭐' * int(obj.average_rating)
        return format_html(
            '<span title="{} reviews">{} {}</span>',
            obj.total_reviews, stars, f"{obj.average_rating:.1f}"
        )
    average_rating_display.short_description = 'Rating'
    
    actions = ['verify_restaurants', 'activate_restaurants', 'deactivate_restaurants']
    
    def verify_restaurants(self, request, queryset):
        """Verify selected restaurants."""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} restaurants verified.')
    verify_restaurants.short_description = 'Verify selected restaurants'
    
    def activate_restaurants(self, request, queryset):
        """Activate selected restaurants."""
        updated = queryset.update(is_active=True, is_accepting_orders=True)
        self.message_user(request, f'{updated} restaurants activated.')
    activate_restaurants.short_description = 'Activate restaurants'
    
    def deactivate_restaurants(self, request, queryset):
        """Deactivate selected restaurants."""
        updated = queryset.update(is_accepting_orders=False)
        self.message_user(request, f'{updated} restaurants deactivated.')
    deactivate_restaurants.short_description = 'Deactivate restaurants'


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    """Admin for MenuItem model."""
    
    list_display = [
        'name', 'restaurant_name', 'category_name', 'price_display',
        'is_available', 'is_featured', 'total_orders'
    ]
    list_filter = [
        'is_available', 'is_featured', 'is_vegetarian',
        'is_vegan', 'is_gluten_free', 'category'
    ]
    search_fields = ['name', 'restaurant__name', 'description']
    readonly_fields = ['slug', 'total_orders', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('restaurant', 'category', 'name', 'slug', 'description', 'image')
        }),
        ('Pricing', {
            'fields': ('price', 'discounted_price')
        }),
        ('Details', {
            'fields': (
                'preparation_time', 'calories',
                'is_vegetarian', 'is_vegan', 'is_gluten_free',
                'spice_level'
            )
        }),
        ('Availability', {
            'fields': ('is_available', 'is_featured', 'stock_quantity')
        }),
        ('Customization', {
            'fields': ('customization_options',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('total_orders',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def restaurant_name(self, obj):
        """Display restaurant name."""
        return obj.restaurant.name
    restaurant_name.short_description = 'Restaurant'
    
    def category_name(self, obj):
        """Display category name."""
        return obj.category.name if obj.category else '-'
    category_name.short_description = 'Category'
    
    def price_display(self, obj):
        """Display price with discount."""
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration: line-through;">₦{}</span> '
                '<span style="color: red; font-weight: bold;">₦{}</span>',
                obj.price, obj.discounted_price
            )
        return f'₦{obj.price}'
    price_display.short_description = 'Price'
    
    actions = ['mark_as_featured', 'mark_as_available', 'mark_as_unavailable']
    
    def mark_as_featured(self, request, queryset):
        """Mark items as featured."""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} items marked as featured.')
    mark_as_featured.short_description = 'Mark as featured'
    
    def mark_as_available(self, request, queryset):
        """Mark items as available."""
        updated = queryset.update(is_available=True)
        self.message_user(request, f'{updated} items marked as available.')
    mark_as_available.short_description = 'Mark as available'
    
    def mark_as_unavailable(self, request, queryset):
        """Mark items as unavailable."""
        updated = queryset.update(is_available=False)
        self.message_user(request, f'{updated} items marked as unavailable.')
    mark_as_unavailable.short_description = 'Mark as unavailable'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin for Review model."""
    
    list_display = [
        'restaurant_name', 'user_name', 'rating_display',
        'created_at'
    ]
    list_filter = ['rating', 'created_at']
    search_fields = [
        'restaurant__name', 'user__username', 'comment'
    ]
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Review Information', {
            'fields': ('restaurant', 'user', 'order', 'rating', 'comment')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def restaurant_name(self, obj):
        """Display restaurant name."""
        return obj.restaurant.name
    restaurant_name.short_description = 'Restaurant'
    
    def user_name(self, obj):
        """Display user name."""
        return obj.user.get_full_name() or obj.user.username
    user_name.short_description = 'User'
    
    def rating_display(self, obj):
        """Display rating with stars."""
        stars = '⭐' * obj.rating
        return stars
    rating_display.short_description = 'Rating'