"""
Admin configuration for core models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import NotificationQueue, SystemSetting


@admin.register(NotificationQueue)
class NotificationQueueAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'notification_type', 'backend', 'recipient_display',
        'status_badge', 'attempts', 'priority', 'created_at', 'scheduled_for'
    ]
    list_filter = ['status', 'backend', 'notification_type', 'priority', 'created_at']
    search_fields = ['recipient', 'recipient_name', 'subject', 'error_message']
    readonly_fields = ['created_at', 'sent_at', 'last_error_at', 'attempts']
    
    fieldsets = (
        ('Notification Info', {
            'fields': ('notification_type', 'backend', 'priority')
        }),
        ('Recipient', {
            'fields': ('recipient', 'recipient_name')
        }),
        ('Message', {
            'fields': ('subject', 'message_data')
        }),
        ('Status', {
            'fields': ('status', 'attempts', 'max_attempts', 'error_message')
        }),
        ('Timing', {
            'fields': ('created_at', 'scheduled_for', 'sent_at', 'last_error_at')
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['retry_failed', 'mark_as_pending', 'cancel_notifications', 'delete_old_sent']
    
    def recipient_display(self, obj):
        """Display recipient with name if available."""
        if obj.recipient_name:
            return f"{obj.recipient_name} ({obj.recipient})"
        return obj.recipient
    recipient_display.short_description = 'Recipient'
    
    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'sent': 'green',
            'failed': 'red',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def retry_failed(self, request, queryset):
        """Retry failed notifications."""
        count = 0
        for notification in queryset.filter(status='failed'):
            if notification.should_retry():
                notification.status = 'pending'
                notification.scheduled_for = timezone.now()
                notification.save()
                count += 1
        
        self.message_user(request, f'Queued {count} notifications for retry.')
    retry_failed.short_description = 'Retry failed notifications'
    
    def mark_as_pending(self, request, queryset):
        """Reset notifications to pending status."""
        count = queryset.update(status='pending', scheduled_for=timezone.now())
        self.message_user(request, f'Marked {count} notifications as pending.')
    mark_as_pending.short_description = 'Mark as pending'
    
    def cancel_notifications(self, request, queryset):
        """Cancel pending/processing notifications."""
        count = queryset.filter(status__in=['pending', 'processing']).update(status='cancelled')
        self.message_user(request, f'Cancelled {count} notifications.')
    cancel_notifications.short_description = 'Cancel notifications'
    
    def delete_old_sent(self, request, queryset):
        """Delete sent notifications older than 30 days."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=30)
        count, _ = queryset.filter(status='sent', sent_at__lt=cutoff).delete()
        self.message_user(request, f'Deleted {count} old notifications.')
    delete_old_sent.short_description = 'Delete old sent (>30 days)'


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_display', 'value_type', 'updated_at']
    search_fields = ['key', 'description']
    list_filter = ['value_type']
    
    fieldsets = (
        (None, {
            'fields': ('key', 'value', 'value_type')
        }),
        ('Details', {
            'fields': ('description', 'updated_at'),
        }),
    )
    
    readonly_fields = ['updated_at']
    
    def value_display(self, obj):
        """Truncate long values."""
        value = str(obj.value)
        if len(value) > 50:
            return f"{value[:50]}..."
        return value
    value_display.short_description = 'Value'
