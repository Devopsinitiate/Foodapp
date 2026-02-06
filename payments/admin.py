"""
Django Admin configuration for Payments app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Payment, Refund, PaymentWebhookLog, SavedCard


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for Payment model."""
    
    list_display = [
        'reference', 'user', 'order_link', 'amount', 'currency',
        'status_badge', 'payment_method', 'initiated_at'
    ]
    list_filter = [
        'status', 'payment_method', 'currency', 'initiated_at'
    ]
    search_fields = [
        'reference', 'paystack_reference', 'user__username',
        'order__order_number'
    ]
    readonly_fields = [
        'reference', 'paystack_reference', 'paystack_access_code',
        'authorization_url', 'initiated_at', 'paid_at', 'failed_at',
        'refunded_at', 'updated_at', 'paystack_response'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('reference', 'user', 'order', 'amount', 'currency')
        }),
        ('Status', {
            'fields': ('status', 'payment_method', 'error_message')
        }),
        ('Paystack Details', {
            'fields': (
                'paystack_reference', 'paystack_access_code',
                'authorization_url', 'paystack_transaction_id'
            )
        }),
        ('Card Information', {
            'fields': ('card_type', 'card_last4', 'card_bin', 'bank')
        }),
        ('Financial Details', {
            'fields': ('transaction_fee',)
        }),
        ('Additional Info', {
            'fields': ('ip_address', 'metadata', 'paystack_response'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (
                'initiated_at', 'paid_at', 'failed_at',
                'refunded_at', 'updated_at'
            )
        }),
    )
    
    def order_link(self, obj):
        """Link to order admin."""
        from django.urls import reverse
        from django.utils.html import format_html
        
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'success': 'green',
            'failed': 'red',
            'cancelled': 'gray',
            'refunded': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_success', 'mark_as_failed', 'initiate_refund']
    
    def mark_as_success(self, request, queryset):
        """Mark selected payments as successful."""
        for payment in queryset:
            if payment.status == 'pending':
                payment.mark_as_success()
        self.message_user(request, f'{queryset.count()} payments marked as successful.')
    mark_as_success.short_description = 'Mark as successful'
    
    def mark_as_failed(self, request, queryset):
        """Mark selected payments as failed."""
        updated = queryset.filter(status='pending').update(status='failed')
        self.message_user(request, f'{updated} payments marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'
    
    def initiate_refund(self, request, queryset):
        """Initiate refunds for selected payments."""
        count = 0
        for payment in queryset:
            if payment.can_be_refunded:
                payment.initiate_refund(reason='Admin initiated refund')
                count += 1
        self.message_user(request, f'{count} refunds initiated.')
    initiate_refund.short_description = 'Initiate refund'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """Admin for Refund model."""
    
    list_display = [
        'id', 'payment_reference', 'amount', 'status_badge',
        'initiated_by', 'created_at'
    ]
    list_filter = ['status', 'created_at']
    search_fields = ['payment__reference', 'reason']
    readonly_fields = [
        'payment', 'created_at', 'processed_at', 'completed_at',
        'paystack_response'
    ]
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('payment', 'amount', 'status', 'reason', 'initiated_by')
        }),
        ('Paystack Details', {
            'fields': ('paystack_refund_id', 'paystack_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at', 'completed_at')
        }),
    )
    
    def payment_reference(self, obj):
        """Display payment reference."""
        return obj.payment.reference
    payment_reference.short_description = 'Payment Reference'
    
    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    actions = ['mark_as_completed']
    
    def mark_as_completed(self, request, queryset):
        """Mark selected refunds as completed."""
        for refund in queryset:
            if refund.status in ['pending', 'processing']:
                refund.mark_as_completed()
        self.message_user(request, f'{queryset.count()} refunds completed.')
    mark_as_completed.short_description = 'Mark as completed'


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    """Admin for PaymentWebhookLog model."""
    
    list_display = [
        'id', 'event', 'payment_reference', 'signature_valid',
        'processed_badge', 'created_at'
    ]
    list_filter = [
        'event', 'signature_valid', 'processed', 'created_at'
    ]
    search_fields = ['event', 'payment__reference']
    readonly_fields = [
        'event', 'payload', 'payment', 'ip_address', 'signature',
        'signature_valid', 'created_at', 'processed_at'
    ]
    
    fieldsets = (
        ('Webhook Information', {
            'fields': ('event', 'payload', 'payment')
        }),
        ('Security', {
            'fields': ('ip_address', 'signature', 'signature_valid')
        }),
        ('Processing', {
            'fields': ('processed', 'processing_error', 'processed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    def payment_reference(self, obj):
        """Display payment reference if exists."""
        return obj.payment.reference if obj.payment else '-'
    payment_reference.short_description = 'Payment'
    
    def processed_badge(self, obj):
        """Processed status badge."""
        if obj.processed:
            color = 'green' if not obj.processing_error else 'orange'
            text = 'Processed' if not obj.processing_error else 'Error'
        else:
            color = 'gray'
            text = 'Pending'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, text
        )
    processed_badge.short_description = 'Processed'
    
    def has_add_permission(self, request):
        """Webhooks are created automatically."""
        return False


@admin.register(SavedCard)
class SavedCardAdmin(admin.ModelAdmin):
    """Admin for SavedCard model."""
    
    list_display = [
        'id', 'user', 'card_display', 'bank', 'is_default',
        'is_expired_badge', 'is_active', 'last_used'
    ]
    list_filter = ['is_default', 'is_active', 'card_type', 'bank']
    search_fields = ['user__username', 'card_last4', 'authorization_code']
    readonly_fields = [
        'authorization_code', 'customer_code', 'created_at', 'last_used'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Card Details', {
            'fields': (
                'authorization_code', 'card_type', 'card_last4',
                'card_bin', 'bank', 'brand', 'exp_month', 'exp_year'
            )
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Metadata', {
            'fields': ('customer_code',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_used')
        }),
    )
    
    def card_display(self, obj):
        """Display card information."""
        return f"{obj.card_type} •••• {obj.card_last4}"
    card_display.short_description = 'Card'
    
    def is_expired_badge(self, obj):
        """Expired status badge."""
        if obj.is_expired:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Expired</span>'
            )
        return format_html(
            '<span style="background-color: green; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Valid</span>'
        )
    is_expired_badge.short_description = 'Expiry Status'
    
    actions = ['deactivate_cards']
    
    def deactivate_cards(self, request, queryset):
        """Deactivate selected cards."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} cards deactivated.')
    deactivate_cards.short_description = 'Deactivate selected cards'