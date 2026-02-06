"""
DRF Serializers for User models.
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    
    class Meta:
        model = UserProfile
        fields = [
            'favorite_cuisines', 'dietary_restrictions',
            'email_notifications', 'sms_notifications', 'push_notifications',
            'total_orders', 'total_spent', 'loyalty_points'
        ]
        read_only_fields = ['total_orders', 'total_spent', 'loyalty_points']


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer."""
    profile = UserProfileSerializer(read_only=True)
    full_address = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'user_type', 'phone_number', 'street_address', 'city',
            'state', 'postal_code', 'latitude', 'longitude',
            'profile_picture', 'bio', 'is_verified', 'full_address',
            'created_at', 'profile'
        ]
        read_only_fields = ['id', 'created_at', 'is_verified']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password2',
            'first_name', 'last_name', 'phone_number',
            'user_type'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value
    
    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        
        user = User.objects.create(**validated_data)
        user.set_password(password)
        user.save()
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone_number',
            'street_address', 'city', 'state', 'postal_code',
            'latitude', 'longitude', 'profile_picture', 'bio'
        ]


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for changing password."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password2 = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({
                "new_password": "Password fields didn't match."
            })
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class VendorSerializer(serializers.ModelSerializer):
    """Serializer specifically for vendor users."""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'email', 'phone_number', 'is_active_vendor',
            'profile_picture', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'is_active_vendor']


class DriverSerializer(serializers.ModelSerializer):
    """Serializer specifically for driver users."""
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'phone_number', 'is_available_driver',
            'profile_picture', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']