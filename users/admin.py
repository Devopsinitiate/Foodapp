"""
Django Admin configuration for Users app
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model."""
    
    list_display = [
        'username', 'email', 'user_type', 'phone_number',
        'is_verified', 'is_active', 'created_at'
    ]
    list_filter = [
        'user_type', 'is_verified', 'is_active',
        'is_active_vendor', 'is_available_driver', 'created_at'
    ]
    search_fields = ['username', 'email', 'phone_number', 'first_name', 'last_name']
    ordering = ['-created_at']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('User Type', {
            'fields': ('user_type',)
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'street_address', 'city', 'state', 'postal_code')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Profile', {
            'fields': ('profile_picture', 'bio')
        }),
        ('Status', {
            'fields': ('is_verified', 'is_active_vendor', 'is_available_driver')
        }),
    )
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('user_type', 'email', 'phone_number')
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    actions = ['verify_users', 'activate_vendors', 'deactivate_vendors']
    
    def verify_users(self, request, queryset):
        """Mark selected users as verified."""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users marked as verified.')
    verify_users.short_description = 'Mark selected users as verified'
    
    def activate_vendors(self, request, queryset):
        """Activate vendor accounts."""
        updated = queryset.filter(user_type='vendor').update(is_active_vendor=True)
        self.message_user(request, f'{updated} vendor accounts activated.')
    activate_vendors.short_description = 'Activate vendor accounts'
    
    def deactivate_vendors(self, request, queryset):
        """Deactivate vendor accounts."""
        updated = queryset.filter(user_type='vendor').update(is_active_vendor=False)
        self.message_user(request, f'{updated} vendor accounts deactivated.')
    deactivate_vendors.short_description = 'Deactivate vendor accounts'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin for UserProfile model."""
    
    list_display = [
        'user', 'total_orders', 'total_spent',
        'loyalty_points', 'email_notifications'
    ]
    list_filter = [
        'email_notifications', 'sms_notifications',
        'push_notifications'
    ]
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['total_orders', 'total_spent', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Preferences', {
            'fields': ('favorite_cuisines', 'dietary_restrictions')
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'sms_notifications', 'push_notifications')
        }),
        ('Statistics', {
            'fields': ('total_orders', 'total_spent', 'loyalty_points'),
            'classes': ('collapse',)
        }),
    )