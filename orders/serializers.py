"""
DRF Serializers for Order models.
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Order, OrderItem, Cart, CartItem, Coupon
from restaurants.models import MenuItem
from restaurants.serializers import MenuItemListSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""
    menu_item = MenuItemListSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'menu_item', 'item_name', 'item_description',
            'price_at_order', 'quantity', 'customizations',
            'special_instructions', 'total_price'
        ]
        read_only_fields = ['id', 'total_price']


class OrderItemCreateSerializer(serializers.Serializer):
    """Serializer for creating order items."""
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    customizations = serializers.JSONField(required=False, default=dict)
    special_instructions = serializers.CharField(required=False, allow_blank=True)
    
    def validate_menu_item_id(self, value):
        try:
            menu_item = MenuItem.objects.get(id=value, is_available=True)
            if not menu_item.is_in_stock():
                raise serializers.ValidationError("Item is out of stock.")
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("Menu item not found or unavailable.")
        return value


class OrderListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for order listing."""
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    restaurant_logo = serializers.ImageField(source='restaurant.logo', read_only=True)
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'restaurant_name', 'restaurant_logo',
            'status', 'payment_status', 'total', 'items_count',
            'created_at', 'estimated_delivery_time'
        ]
    
    def get_items_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for order."""
    items = OrderItemSerializer(many=True, read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    restaurant_phone = serializers.CharField(source='restaurant.phone_number', read_only=True)
    full_delivery_address = serializers.CharField(read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user', 'restaurant_name',
            'restaurant_phone', 'status', 'payment_status',
            'full_delivery_address', 'delivery_instructions',
            'contact_phone', 'contact_email', 'subtotal',
            'delivery_fee', 'tax', 'discount', 'total',
            'coupon_code', 'estimated_delivery_time',
            'confirmed_at', 'delivered_at', 'created_at',
            'special_requests', 'items', 'can_be_cancelled'
        ]
        read_only_fields = [
            'id', 'order_number', 'confirmed_at', 'delivered_at', 'created_at'
        ]


class OrderCreateSerializer(serializers.Serializer):
    """Serializer for creating orders."""
    restaurant_id = serializers.IntegerField()
    items = OrderItemCreateSerializer(many=True)
    delivery_type = serializers.ChoiceField(choices=['delivery', 'pickup'], default='delivery')
    delivery_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    delivery_city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    delivery_state = serializers.CharField(max_length=100, required=False, allow_blank=True)
    delivery_postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True)
    delivery_latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True
    )
    delivery_longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True
    )
    delivery_instructions = serializers.CharField(
        required=False,
        allow_blank=True
    )
    contact_phone = serializers.CharField(max_length=17)
    contact_email = serializers.EmailField()
    special_requests = serializers.CharField(
        required=False,
        allow_blank=True
    )
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True
    )
    
    def validate(self, data):
        """Validate address fields if delivery_type is 'delivery'."""
        if data.get('delivery_type') == 'delivery':
            required_fields = ['delivery_address', 'delivery_city', 'delivery_state']
            for field in required_fields:
                if not data.get(field):
                    raise serializers.ValidationError({field: "This field is required for delivery orders."})
        return data

    def validate_restaurant_id(self, value):
        from restaurants.models import Restaurant
        try:
            restaurant = Restaurant.objects.get(
                id=value,
                is_active=True,
                is_accepting_orders=True
            )
        except Restaurant.DoesNotExist:
            raise serializers.ValidationError(
                "Restaurant not found or not accepting orders."
            )
        return value
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must contain at least one item.")
        return value
    
    def validate_coupon_code(self, value):
        if value:
            try:
                coupon = Coupon.objects.get(code=value)
                if not coupon.is_valid():
                    raise serializers.ValidationError("Coupon is not valid.")
            except Coupon.DoesNotExist:
                raise serializers.ValidationError("Coupon not found.")
        return value
    
    def create(self, validated_data):
        from restaurants.models import Restaurant
        from decimal import Decimal
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            user = self.context['request'].user
            items_data = validated_data.pop('items')
            restaurant = Restaurant.objects.get(id=validated_data.pop('restaurant_id'))
            coupon_code = validated_data.pop('coupon_code', None)
            
            # Calculate subtotal
            subtotal = Decimal('0.00')
            order_items = []
            
            for item_data in items_data:
                menu_item = MenuItem.objects.get(id=item_data['menu_item_id'])
                price = menu_item.current_price
                quantity = item_data['quantity']
                item_total = price * quantity
                subtotal += item_total
                
                order_items.append({
                    'menu_item': menu_item,
                    'item_name': menu_item.name,
                    'item_description': menu_item.description,
                    'price_at_order': price,
                    'quantity': quantity,
                    'customizations': item_data.get('customizations', {}),
                    'special_instructions': item_data.get('special_instructions', ''),
                    'total_price': item_total
                })
            
            # Calculate fees and discounts
            delivery_type = validated_data.get('delivery_type', 'delivery')
            delivery_fee = Decimal('0.00') if delivery_type == 'pickup' else restaurant.delivery_fee
            tax = subtotal * Decimal('0.08')  # 8% tax
            discount = Decimal('0.00')
            
            if coupon_code:
                coupon = Coupon.objects.get(code=coupon_code)
                if subtotal >= coupon.minimum_order_amount:
                    discount = coupon.calculate_discount(subtotal)
                    coupon.times_used += 1
                    coupon.save()
            
            total = subtotal + delivery_fee + tax - discount
            
            # Create order
            order = Order.objects.create(
                user=user,
                restaurant=restaurant,
                subtotal=subtotal,
                delivery_fee=delivery_fee,
                tax=tax,
                discount=discount,
                total=total,
                coupon_code=coupon_code or '',
                **validated_data
            )
            
            # Create order items
            for item_data in order_items:
                OrderItem.objects.create(order=order, **item_data)
            
            # Set estimated delivery time
            estimated_time = timezone.now() + timezone.timedelta(
                minutes=restaurant.estimated_delivery_time
            )
            order.estimated_delivery_time = estimated_time
            order.save()
            
            # Send email notifications
            try:
                from users.emails import send_order_confirmation_email, send_new_order_notification_to_vendor
                logger.info(f"Sending email notifications for order {order.order_number}")
                
                # Send confirmation to customer
                customer_email_sent = send_order_confirmation_email(order)
                if customer_email_sent:
                    logger.info(f"Order confirmation email sent to {order.user.email}")
                else:
                    logger.warning(f"Failed to send confirmation email to {order.user.email}")
                
                # Send notification to vendor
                vendor_email_sent = send_new_order_notification_to_vendor(order)
                if vendor_email_sent:
                    logger.info(f"Vendor notification sent to {restaurant.owner.email}")
                else:
                    logger.warning(f"Failed to send vendor notification to {restaurant.owner.email}")
                    
            except Exception as email_error:
                # Log error but don't fail order creation
                logger.error(f"Error sending order emails: {str(email_error)}", exc_info=True)
            
            return order
            
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}", exc_info=True)
            raise serializers.ValidationError(f"Error creating order: {str(e)}")


class OrderUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating order status (vendor/admin use)."""
    
    class Meta:
        model = Order
        fields = ['status', 'special_requests']
    
    def validate_status(self, value):
        order = self.instance
        valid_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['preparing', 'cancelled'],
            'preparing': ['ready', 'cancelled'],
            'ready': ['out_for_delivery'],
            'out_for_delivery': ['delivered', 'cancelled'],
        }
        
        if order.status not in valid_transitions:
            raise serializers.ValidationError(
                f"Cannot update order in {order.status} status."
            )
        
        if value not in valid_transitions[order.status]:
            raise serializers.ValidationError(
                f"Invalid status transition from {order.status} to {value}."
            )
        
        return value


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for cart items."""
    menu_item = MenuItemListSerializer(read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = CartItem
        fields = [
            'id', 'menu_item', 'quantity', 'customizations',
            'total_price', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CartItemCreateSerializer(serializers.Serializer):
    """Serializer for adding items to cart."""
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    customizations = serializers.JSONField(required=False, default=dict)
    
    def validate_menu_item_id(self, value):
        try:
            menu_item = MenuItem.objects.get(id=value, is_available=True)
            if not menu_item.is_in_stock():
                raise serializers.ValidationError("Item is out of stock.")
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("Menu item not found or unavailable.")
        return value


class CartSerializer(serializers.ModelSerializer):
    """Serializer for shopping cart."""
    cart_items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = Cart
        fields = [
            'id', 'cart_items', 'total_items', 'subtotal',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for coupons."""
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'description', 'discount_type',
            'discount_value', 'minimum_order_amount', 'max_uses',
            'times_used', 'valid_from', 'valid_until', 'is_valid'
        ]
        read_only_fields = ['id', 'times_used']
    
    def get_is_valid(self, obj):
        return obj.is_valid()


class CouponValidateSerializer(serializers.Serializer):
    """Serializer for validating coupon codes."""
    code = serializers.CharField()
    order_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def validate_code(self, value):
        try:
            coupon = Coupon.objects.get(code=value)
            if not coupon.is_valid():
                raise serializers.ValidationError("Coupon is not valid.")
            self.context['coupon'] = coupon
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Coupon not found.")
        return value
    
    def validate(self, attrs):
        coupon = self.context['coupon']
        order_total = attrs['order_total']
        
        if order_total < coupon.minimum_order_amount:
            raise serializers.ValidationError({
                'order_total': f"Minimum order amount is {coupon.minimum_order_amount}"
            })
        
        return attrs