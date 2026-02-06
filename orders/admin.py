"""
Django Admin configuration for Orders app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, Cart, CartItem, Coupon


class OrderItemInline(admin.TabularInline):
    """Inline for order items."""
    model = OrderItem
    extra = 0
    readonly_fields = ['item_name', 'price_at_order', 'quantity', 'total_price']
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin for Order model."""
    
    list_display = [
        'order_number', 'user_name', 'restaurant_name',
        'status_badge', 'payment_status_badge', 'total',
        'created_at'
    ]
    list_filter = [
        'status', 'payment_status', 'created_at',
        'confirmed_at', 'delivered_at'
    ]
    search_fields = [
        'order_number', 'user__username', 'restaurant__name',
        'contact_phone', 'contact_email'
    ]
    readonly_fields = [
        'order_number', 'created_at', 'updated_at',
        'confirmed_at', 'delivered_at'
    ]
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'restaurant')
        }),
        ('Status', {
            'fields': ('status', 'payment_status')
        }),
        ('Delivery Information', {
            'fields': (
                'delivery_address', 'delivery_city', 'delivery_state',
                'delivery_postal_code', 'delivery_latitude',
                'delivery_longitude', 'delivery_instructions'
            )
        }),
        ('Contact', {
            'fields': ('contact_phone', 'contact_email')
        }),
        ('Pricing', {
            'fields': (
                'subtotal', 'delivery_fee', 'tax',
                'discount', 'total', 'coupon_code'
            )
        }),
        ('Timing', {
            'fields': (
                'estimated_delivery_time', 'confirmed_at', 'delivered_at'
            )
        }),
        ('Notes', {
            'fields': ('special_requests', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_name(self, obj):
        """Display user name."""
        return obj.user.get_full_name() or obj.user.username
    user_name.short_description = 'Customer'
    
    def restaurant_name(self, obj):
        """Display restaurant name."""
        return obj.restaurant.name
    restaurant_name.short_description = 'Restaurant'
    
    def status_badge(self, obj):
        """Colored status badge."""
        colors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'preparing': 'purple',
            'ready': 'teal',
            'out_for_delivery': 'indigo',
            'delivered': 'green',
            'cancelled': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Order Status'
    
    def payment_status_badge(self, obj):
        """Colored payment status badge."""
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'failed': 'red',
            'refunded': 'purple',
        }
        color = colors.get(obj.payment_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment Status'
    
    actions = ['confirm_orders', 'mark_as_delivered', 'cancel_orders']
    
    def confirm_orders(self, request, queryset):
        """Confirm selected orders."""
        count = 0
        for order in queryset.filter(status='pending'):
            order.mark_as_confirmed()
            count += 1
        self.message_user(request, f'{count} orders confirmed.')
    confirm_orders.short_description = 'Confirm orders'
    
    def mark_as_delivered(self, request, queryset):
        """Mark orders as delivered."""
        count = 0
        for order in queryset:
            if order.status != 'delivered':
                order.mark_as_delivered()
                count += 1
        self.message_user(request, f'{count} orders marked as delivered.')
    mark_as_delivered.short_description = 'Mark as delivered'
    
    def cancel_orders(self, request, queryset):
        """Cancel selected orders."""
        updated = queryset.filter(
            status__in=['pending', 'confirmed']
        ).update(status='cancelled')
        self.message_user(request, f'{updated} orders cancelled.')
    cancel_orders.short_description = 'Cancel orders'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin for OrderItem model."""
    
    list_display = [
        'order_number', 'item_name', 'quantity',
        'price_at_order', 'total_price'
    ]
    list_filter = ['created_at']
    search_fields = ['order__order_number', 'item_name']
    readonly_fields = ['order', 'menu_item', 'total_price', 'created_at']
    
    def order_number(self, obj):
        """Display order number."""
        return obj.order.order_number
    order_number.short_description = 'Order'


class CartItemInline(admin.TabularInline):
    """Inline for cart items."""
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin for Cart model."""
    
    list_display = [
        'id', 'user_display', 'total_items_display',
        'subtotal_display', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'session_key']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [CartItemInline]
    
    def user_display(self, obj):
        """Display user or session."""
        if obj.user:
            return obj.user.username
        return f"Session: {obj.session_key[:10]}..."
    user_display.short_description = 'User'
    
    def total_items_display(self, obj):
        """Display total items."""
        return obj.total_items
    total_items_display.short_description = 'Items'
    
    def subtotal_display(self, obj):
        """Display subtotal."""
        return f"₦{obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'
    
    actions = ['clear_carts']
    
    def clear_carts(self, request, queryset):
        """Clear selected carts."""
        for cart in queryset:
            cart.clear()
        self.message_user(request, f'{queryset.count()} carts cleared.')
    clear_carts.short_description = 'Clear carts'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """Admin for CartItem model."""
    
    list_display = [
        'cart_id', 'menu_item_name', 'quantity',
        'total_price_display', 'updated_at'
    ]
    list_filter = ['created_at', 'updated_at']
    search_fields = ['menu_item__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def cart_id(self, obj):
        """Display cart ID."""
        return obj.cart.id
    cart_id.short_description = 'Cart'
    
    def menu_item_name(self, obj):
        """Display menu item name."""
        return obj.menu_item.name
    menu_item_name.short_description = 'Item'
    
    def total_price_display(self, obj):
        """Display total price."""
        return f"₦{obj.total_price:.2f}"
    total_price_display.short_description = 'Total'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """Admin for Coupon model."""
    
    list_display = [
        'code', 'discount_display', 'scope', 'usage_count',
        'max_total_uses', 'is_active_badge', 'valid_until'
    ]
    list_filter = [
        'discount_type', 'scope', 'is_active', 'valid_from', 'valid_until'
    ]
    search_fields = ['code', 'description']
    readonly_fields = ['created_at', 'updated_at', 'usage_count']
    autocomplete_fields = ['restaurant', 'created_by']
    
    fieldsets = (
        ('Coupon Information', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Discount', {
            'fields': (
                'discount_type', 'discount_value', 'max_discount_amount'
            )
        }),
        ('Scope', {
            'fields': ('scope', 'restaurant')
        }),
        ('Restrictions', {
            'fields': (
                'min_order_amount', 'first_order_only'
            )
        }),
        ('Usage Limits', {
            'fields': (
                'max_total_uses', 'max_uses_per_user', 'usage_count'
            )
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_until')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def discount_display(self, obj):
        """Display discount."""
        return obj.get_discount_display()
    discount_display.short_description = 'Discount'
    
    def usage_count(self, obj):
        """Display usage count."""
        return obj.get_usage_count()
    usage_count.short_description = 'Times Used'
    
    def is_active_badge(self, obj):
        """Active status badge."""
        if obj.is_active and obj.is_valid_for_date():
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 10px; '
                'border-radius: 3px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: red; color: white; padding: 3px 10px; '
            'border-radius: 3px;">Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    actions = ['activate_coupons', 'deactivate_coupons']
    
    def activate_coupons(self, request, queryset):
        """Activate selected coupons."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} coupons activated.')
    activate_coupons.short_description = 'Activate coupons'
    
    def deactivate_coupons(self, request, queryset):
        """Deactivate selected coupons."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} coupons deactivated.')
    deactivate_coupons.short_description = 'Deactivate coupons'


# Register CouponUsage model
from .models import CouponUsage

@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    """Admin for CouponUsage tracking."""
    
    list_display = [
        'coupon_code', 'user_name', 'order_number',
        'discount_amount', 'used_at'
    ]
    list_filter = ['used_at', 'coupon']
    search_fields = ['coupon__code', 'user__username', 'order__order_number']
    readonly_fields = ['coupon', 'user', 'order', 'discount_amount', 'used_at']
    
    def coupon_code(self, obj):
        return obj.coupon.code
    coupon_code.short_description = 'Coupon'
    
    def user_name(self, obj):
        return obj.user.username
    user_name.short_description = 'User'
    
    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order'
