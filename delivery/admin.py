"""
Django Admin configuration for Delivery app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Delivery, DeliveryLocation, DriverAvailability, DeliveryZone


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    """Admin for Delivery model."""
    
    list_display = [
        'id', 'order_number', 'driver_name', 'status_badge',
        'distance_km', 'estimated_delivery_time', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'actual_delivery_time']
    search_fields = [
        'order__order_number', 'driver__username',
        'order__user__username'
    ]
    readonly_fields = [
        'order', 'assigned_at', 'accepted_at', 'actual_pickup_time',
        'actual_delivery_time', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order',)
        }),
        ('Driver Assignment', {
            'fields': ('driver', 'status', 'assigned_at', 'accepted_at')
        }),
        ('Pickup Location', {
            'fields': ('pickup_latitude', 'pickup_longitude')
        }),
        ('Delivery Location', {
            'fields': (
                'delivery_latitude', 'delivery_longitude',
                'delivery_instructions'
            )
        }),
        ('Current Location', {
            'fields': ('current_latitude', 'current_longitude')
        }),
        ('Timing', {
            'fields': (
                'estimated_pickup_time', 'actual_pickup_time',
                'estimated_delivery_time', 'actual_delivery_time',
                'estimated_duration_minutes'
            )
        }),
        ('Distance', {
            'fields': ('distance_km',)
        }),
        ('Delivery Details', {
            'fields': (
                'delivery_photo', 'signature', 'driver_notes',
                'cancellation_reason'
            )
        }),
        ('Rating', {
            'fields': ('rating', 'feedback')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def order_number(self, obj):
        """Display order number."""
        return obj.order.order_number
    order_number.short_description = 'Order'
    
    def driver_name(self, obj):
        """Display driver name."""
        return obj.driver.get_full_name() if obj.driver else 'Unassigned'
    driver_name.short_description = 'Driver'
    
    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'pending': 'orange',
            'assigned': 'blue',
            'accepted': 'purple',
            'picked_up': 'indigo',
            'en_route': 'teal',
            'arrived': 'cyan',
            'delivered': 'green',
            'cancelled': 'red',
            'failed': 'darkred',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['assign_to_me', 'mark_as_delivered']
    
    def assign_to_me(self, request, queryset):
        """Assign selected deliveries to current user."""
        if not request.user.is_driver:
            self.message_user(request, 'Only drivers can accept deliveries.', level='error')
            return
        
        count = 0
        for delivery in queryset.filter(status='pending'):
            delivery.assign_to_driver(request.user)
            count += 1
        
        self.message_user(request, f'{count} deliveries assigned to you.')
    assign_to_me.short_description = 'Assign to me'
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected deliveries as delivered."""
        count = 0
        for delivery in queryset:
            if delivery.is_active:
                delivery.mark_delivered()
                count += 1
        
        self.message_user(request, f'{count} deliveries marked as delivered.')
    mark_as_delivered.short_description = 'Mark as delivered'


@admin.register(DeliveryLocation)
class DeliveryLocationAdmin(admin.ModelAdmin):
    """Admin for DeliveryLocation model."""
    
    list_display = [
        'id', 'delivery_id', 'latitude', 'longitude',
        'speed', 'timestamp'
    ]
    list_filter = ['timestamp']
    search_fields = ['delivery__order__order_number']
    readonly_fields = ['delivery', 'timestamp']
    
    fieldsets = (
        ('Delivery', {
            'fields': ('delivery',)
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'accuracy')
        }),
        ('Movement', {
            'fields': ('speed', 'heading')
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        }),
    )
    
    def has_add_permission(self, request):
        """Locations are created automatically."""
        return False


@admin.register(DriverAvailability)
class DriverAvailabilityAdmin(admin.ModelAdmin):
    """Admin for DriverAvailability model."""
    
    list_display = [
        'driver_name', 'is_online_badge', 'is_available_badge',
        'vehicle_type', 'total_deliveries', 'success_rate_display',
        'average_rating', 'last_online'
    ]
    list_filter = [
        'is_online', 'is_available', 'vehicle_type',
        'last_online'
    ]
    search_fields = ['driver__username', 'driver__email', 'vehicle_plate']
    readonly_fields = [
        'total_deliveries', 'successful_deliveries',
        'cancelled_deliveries', 'average_rating',
        'last_online', 'last_location_update', 'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Driver', {
            'fields': ('driver',)
        }),
        ('Availability', {
            'fields': ('is_available', 'is_online')
        }),
        ('Location', {
            'fields': ('current_latitude', 'current_longitude')
        }),
        ('Vehicle', {
            'fields': ('vehicle_type', 'vehicle_plate')
        }),
        ('Statistics', {
            'fields': (
                'total_deliveries', 'successful_deliveries',
                'cancelled_deliveries', 'average_rating'
            )
        }),
        ('Activity', {
            'fields': ('last_online', 'last_location_update')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def driver_name(self, obj):
        """Display driver name."""
        return obj.driver.get_full_name() or obj.driver.username
    driver_name.short_description = 'Driver'
    
    def is_online_badge(self, obj):
        """Online status badge."""
        if obj.is_online:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Online</span>'
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Offline</span>'
        )
    is_online_badge.short_description = 'Status'
    
    def is_available_badge(self, obj):
        """Available status badge."""
        if obj.is_available:
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Available</span>'
            )
        return format_html(
            '<span style="background-color: orange; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Busy</span>'
        )
    is_available_badge.short_description = 'Availability'
    
    def success_rate_display(self, obj):
        """Display success rate."""
        return f"{obj.success_rate:.1f}%"
    success_rate_display.short_description = 'Success Rate'
    
    actions = ['set_online', 'set_offline']
    
    def set_online(self, request, queryset):
        """Set drivers as online."""
        for availability in queryset:
            availability.go_online()
        self.message_user(request, f'{queryset.count()} drivers set online.')
    set_online.short_description = 'Set as online'
    
    def set_offline(self, request, queryset):
        """Set drivers as offline."""
        for availability in queryset:
            availability.go_offline()
        self.message_user(request, f'{queryset.count()} drivers set offline.')
    set_offline.short_description = 'Set as offline'


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    """Admin for DeliveryZone model."""
    
    list_display = [
        'name', 'radius_km', 'base_delivery_fee',
        'per_km_rate', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Zone Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Geographic Boundaries', {
            'fields': (
                'center_latitude', 'center_longitude', 'radius_km'
            )
        }),
        ('Pricing', {
            'fields': ('base_delivery_fee', 'per_km_rate')
        }),
        ('Operating Hours', {
            'fields': ('operating_hours',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )