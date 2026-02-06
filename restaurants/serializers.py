"""
DRF Serializers for Restaurant models.
"""
from rest_framework import serializers
from .models import Category, Restaurant, MenuItem, Review
from users.serializers import VendorSerializer


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon', 'is_active', 'order']
        read_only_fields = ['id', 'slug']


class MenuItemListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for menu item listing."""
    category_name = serializers.CharField(source='category.name', read_only=True)
    current_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_on_sale = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'slug', 'description', 'image',
            'price', 'discounted_price', 'current_price', 'is_on_sale',
            'category_name', 'is_available', 'is_featured',
            'is_vegetarian', 'is_vegan', 'is_gluten_free',
            'preparation_time', 'calories', 'spice_level'
        ]


class MenuItemDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for menu item."""
    category = CategorySerializer(read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    current_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    is_on_sale = serializers.BooleanField(read_only=True)
    is_in_stock = serializers.SerializerMethodField()
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'restaurant_name', 'category', 'name', 'slug',
            'description', 'image', 'price', 'discounted_price',
            'current_price', 'is_on_sale', 'preparation_time',
            'calories', 'is_vegetarian', 'is_vegan', 'is_gluten_free',
            'spice_level', 'is_available', 'is_featured', 'is_in_stock',
            'stock_quantity', 'customization_options', 'total_orders',
            'created_at'
        ]
        read_only_fields = ['id', 'slug', 'total_orders', 'created_at']
    
    def get_is_in_stock(self, obj):
        return obj.is_in_stock()


class MenuItemCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating menu items (vendor use)."""
    
    class Meta:
        model = MenuItem
        fields = [
            'category', 'name', 'description', 'image',
            'price', 'discounted_price', 'preparation_time',
            'calories', 'is_vegetarian', 'is_vegan', 'is_gluten_free',
            'spice_level', 'is_available', 'is_featured',
            'stock_quantity', 'customization_options'
        ]
    
    def validate(self, attrs):
        # Ensure discounted price is less than regular price
        if attrs.get('discounted_price'):
            if attrs['discounted_price'] >= attrs['price']:
                raise serializers.ValidationError({
                    'discounted_price': 'Discounted price must be less than regular price.'
                })
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model."""
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_avatar = serializers.ImageField(source='user.profile_picture', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'user_name', 'user_avatar', 'rating',
            'comment', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user_name', 'user_avatar', 'created_at', 'updated_at']


class ReviewCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating reviews."""
    
    class Meta:
        model = Review
        fields = ['rating', 'comment', 'order']
    
    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        validated_data['restaurant'] = self.context['restaurant']
        return super().create(validated_data)


class RestaurantListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for restaurant listing."""
    categories = CategorySerializer(many=True, read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'slug', 'logo', 'cover_image',
            'cuisine_type', 'categories', 'average_rating',
            'total_reviews', 'delivery_fee', 'minimum_order',
            'estimated_delivery_time', 'is_accepting_orders',
            'city'
        ]


class RestaurantDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for restaurant."""
    owner = VendorSerializer(read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    menu_items = MenuItemListSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    full_address = serializers.CharField(read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'owner', 'name', 'slug', 'description',
            'logo', 'cover_image', 'phone_number', 'email',
            'full_address', 'latitude', 'longitude',
            'categories', 'cuisine_type', 'business_hours',
            'average_rating', 'total_reviews', 'delivery_fee',
            'minimum_order', 'estimated_delivery_time',
            'delivery_radius', 'is_active', 'is_accepting_orders',
            'is_verified', 'total_orders', 'menu_items', 'reviews',
            'created_at'
        ]
        read_only_fields = [
            'id', 'slug', 'average_rating', 'total_reviews',
            'total_orders', 'created_at', 'is_verified'
        ]


class RestaurantCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating restaurants (vendor use)."""
    
    class Meta:
        model = Restaurant
        fields = [
            'name', 'description', 'logo', 'cover_image',
            'phone_number', 'email', 'street_address', 'city',
            'state', 'postal_code', 'latitude', 'longitude',
            'cuisine_type', 'business_hours', 'delivery_fee',
            'minimum_order', 'estimated_delivery_time',
            'delivery_radius', 'is_accepting_orders'
        ]
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class RestaurantStatsSerializer(serializers.Serializer):
    """Serializer for restaurant statistics."""
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_menu_items = serializers.IntegerField()
    active_menu_items = serializers.IntegerField()
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_reviews = serializers.IntegerField()