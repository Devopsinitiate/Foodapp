"""
DRF Serializers for Delivery models.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Delivery, DeliveryLocation, DriverAvailability, DeliveryZone
from orders.serializers import OrderListSerializer
from users.serializers import DriverSerializer

User = get_user_model()


class DeliveryLocationSerializer(serializers.ModelSerializer):
    """Serializer for delivery location tracking."""
    
    class Meta:
        model = DeliveryLocation
        fields = [
            'id', 'latitude', 'longitude', 'speed',
            'heading', 'accuracy', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class DeliveryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for delivery listing."""
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.user.username', read_only=True)
    restaurant_name = serializers.CharField(source='order.restaurant.name', read_only=True)
    driver_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order_number', 'customer_name', 'restaurant_name',
            'driver_name', 'status', 'estimated_delivery_time',
            'created_at'
        ]
    
    def get_driver_name(self, obj):
        """Get driver name if assigned."""
        if obj.driver:
            return obj.driver.get_full_name() or obj.driver.username
        return None


class DeliveryDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for delivery information."""
    order = OrderListSerializer(read_only=True)
    driver = DriverSerializer(read_only=True)
    location_history = DeliveryLocationSerializer(many=True, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    
    # Location details
    pickup_location = serializers.SerializerMethodField()
    delivery_location = serializers.SerializerMethodField()
    current_location = serializers.SerializerMethodField()
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'driver', 'status',
            'pickup_location', 'delivery_location', 'current_location',
            'estimated_pickup_time', 'actual_pickup_time',
            'estimated_delivery_time', 'actual_delivery_time',
            'distance_km', 'estimated_duration_minutes',
            'delivery_instructions', 'delivery_photo', 'signature',
            'driver_notes', 'rating', 'feedback',
            'assigned_at', 'accepted_at', 'is_active', 'is_completed',
            'location_history', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'assigned_at', 'accepted_at', 'created_at', 'updated_at'
        ]
    
    def get_pickup_location(self, obj):
        """Get pickup location coordinates."""
        if obj.pickup_latitude and obj.pickup_longitude:
            return {
                'latitude': float(obj.pickup_latitude),
                'longitude': float(obj.pickup_longitude)
            }
        return None
    
    def get_delivery_location(self, obj):
        """Get delivery location coordinates."""
        if obj.delivery_latitude and obj.delivery_longitude:
            return {
                'latitude': float(obj.delivery_latitude),
                'longitude': float(obj.delivery_longitude)
            }
        return None
    
    def get_current_location(self, obj):
        """Get current driver location."""
        if obj.current_latitude and obj.current_longitude:
            return {
                'latitude': float(obj.current_latitude),
                'longitude': float(obj.current_longitude)
            }
        return None


class DeliveryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating delivery records."""
    
    class Meta:
        model = Delivery
        fields = [
            'order', 'pickup_latitude', 'pickup_longitude',
            'delivery_latitude', 'delivery_longitude',
            'delivery_instructions', 'estimated_delivery_time',
            'distance_km', 'estimated_duration_minutes'
        ]
    
    def validate_order(self, value):
        """Ensure order doesn't already have a delivery."""
        if hasattr(value, 'delivery'):
            raise serializers.ValidationError(
                "This order already has a delivery assigned."
            )
        return value


class DeliveryUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating delivery status."""
    
    class Meta:
        model = Delivery
        fields = [
            'status', 'driver_notes', 'delivery_photo',
            'signature', 'cancellation_reason'
        ]
    
    def validate_status(self, value):
        """Validate status transitions."""
        instance = self.instance
        if not instance:
            return value
        
        valid_transitions = {
            'pending': ['assigned', 'cancelled'],
            'assigned': ['accepted', 'cancelled'],
            'accepted': ['picked_up', 'cancelled'],
            'picked_up': ['en_route'],
            'en_route': ['arrived'],
            'arrived': ['delivered', 'failed'],
        }
        
        current_status = instance.status
        if current_status not in valid_transitions:
            raise serializers.ValidationError(
                f"Cannot update delivery in {current_status} status."
            )
        
        if value not in valid_transitions[current_status]:
            raise serializers.ValidationError(
                f"Invalid status transition from {current_status} to {value}."
            )
        
        return value


class DeliveryLocationUpdateSerializer(serializers.Serializer):
    """Serializer for updating driver location."""
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    speed = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False,
        allow_null=True
    )
    heading = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False,
        allow_null=True
    )
    accuracy = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        required=False,
        allow_null=True
    )


class DriverAvailabilitySerializer(serializers.ModelSerializer):
    """Serializer for driver availability."""
    driver = DriverSerializer(read_only=True)
    current_location = serializers.SerializerMethodField()
    success_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = DriverAvailability
        fields = [
            'id', 'driver', 'is_available', 'is_online',
            'current_location', 'total_deliveries',
            'successful_deliveries', 'cancelled_deliveries',
            'average_rating', 'success_rate', 'vehicle_type',
            'vehicle_plate', 'last_online', 'last_location_update'
        ]
        read_only_fields = [
            'id', 'total_deliveries', 'successful_deliveries',
            'cancelled_deliveries', 'average_rating', 'last_online',
            'last_location_update'
        ]
    
    def get_current_location(self, obj):
        """Get current location coordinates."""
        if obj.current_latitude and obj.current_longitude:
            return {
                'latitude': float(obj.current_latitude),
                'longitude': float(obj.current_longitude)
            }
        return None


class DriverAvailabilityUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating driver availability."""
    
    class Meta:
        model = DriverAvailability
        fields = [
            'is_available', 'is_online', 'vehicle_type', 'vehicle_plate'
        ]


class DriverStatsSerializer(serializers.Serializer):
    """Serializer for driver statistics."""
    total_deliveries = serializers.IntegerField()
    successful_deliveries = serializers.IntegerField()
    cancelled_deliveries = serializers.IntegerField()
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    deliveries_today = serializers.IntegerField()
    earnings_today = serializers.DecimalField(max_digits=10, decimal_places=2)


class DeliveryZoneSerializer(serializers.ModelSerializer):
    """Serializer for delivery zones."""
    center_location = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliveryZone
        fields = [
            'id', 'name', 'description', 'center_location',
            'radius_km', 'base_delivery_fee', 'per_km_rate',
            'is_active', 'operating_hours', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_center_location(self, obj):
        """Get zone center coordinates."""
        return {
            'latitude': float(obj.center_latitude),
            'longitude': float(obj.center_longitude)
        }


class DeliveryZoneCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating delivery zones."""
    
    class Meta:
        model = DeliveryZone
        fields = [
            'name', 'description', 'center_latitude', 'center_longitude',
            'radius_km', 'base_delivery_fee', 'per_km_rate',
            'operating_hours', 'is_active'
        ]
    
    def validate_radius_km(self, value):
        """Validate radius is reasonable."""
        if value <= 0:
            raise serializers.ValidationError("Radius must be greater than 0.")
        if value > 100:
            raise serializers.ValidationError("Radius cannot exceed 100 km.")
        return value


class AssignDeliverySerializer(serializers.Serializer):
    """Serializer for assigning delivery to driver."""
    driver_id = serializers.IntegerField()
    
    def validate_driver_id(self, value):
        """Validate driver exists and is available."""
        try:
            driver = User.objects.get(id=value, user_type='driver')
            
            # Check if driver is available
            try:
                availability = DriverAvailability.objects.get(driver=driver)
                if not availability.is_available:
                    raise serializers.ValidationError(
                        "Driver is not available for deliveries."
                    )
            except DriverAvailability.DoesNotExist:
                raise serializers.ValidationError(
                    "Driver availability record not found."
                )
            
        except User.DoesNotExist:
            raise serializers.ValidationError("Driver not found.")
        
        return value


class DeliveryRatingSerializer(serializers.Serializer):
    """Serializer for rating a delivery."""
    rating = serializers.IntegerField(min_value=1, max_value=5)
    feedback = serializers.CharField(required=False, allow_blank=True)
    
    def validate_rating(self, value):
        """Validate rating is between 1 and 5."""
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class NearbyDriverSerializer(serializers.Serializer):
    """Serializer for nearby available drivers."""
    driver_id = serializers.IntegerField()
    driver_name = serializers.CharField()
    distance_km = serializers.DecimalField(max_digits=5, decimal_places=2)
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_deliveries = serializers.IntegerField()
    success_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    vehicle_type = serializers.CharField()
    current_location = serializers.DictField()


class DeliveryETASerializer(serializers.Serializer):
    """Serializer for delivery ETA calculation."""
    estimated_arrival = serializers.DateTimeField()
    distance_remaining_km = serializers.DecimalField(max_digits=5, decimal_places=2)
    estimated_minutes = serializers.IntegerField()


class DeliveryHistorySerializer(serializers.ModelSerializer):
    """Serializer for delivery history (simplified)."""
    order_number = serializers.CharField(source='order.order_number')
    customer_name = serializers.CharField(source='order.user.username')
    restaurant_name = serializers.CharField(source='order.restaurant.name')
    driver_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Delivery
        fields = [
            'id', 'order_number', 'customer_name', 'restaurant_name',
            'driver_name', 'status', 'rating', 'actual_delivery_time',
            'created_at'
        ]
    
    def get_driver_name(self, obj):
        """Get driver name if assigned."""
        if obj.driver:
            return obj.driver.get_full_name() or obj.driver.username
        return 'Unassigned'