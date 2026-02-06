"""
Order assignment logic for automatically assigning deliveries to drivers.
"""
from django.db.models import Q
from django.utils import timezone
from delivery.models import Delivery, DriverAvailability
from orders.models import Order
from users.models import User
import math


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula (in km)."""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def find_available_drivers(restaurant_lat, restaurant_lon, radius_km=10):
    """Find all available drivers within a specified radius of the restaurant."""
    # Get all online drivers who are:
    # 1. Online (is_online=True)
    # 2. Either available OR have no active deliveries (to handle edge cases)
    # 3. Verified and active
    available_drivers = DriverAvailability.objects.filter(
        is_online=True,
        driver__is_verified_driver=True,
        driver__is_active=True
    ).select_related('driver')
    
    # Further filter to get truly available drivers
    from delivery.models import Delivery
    truly_available = []
    for availability in available_drivers:
        # Check if driver has any active deliveries
        active_delivery_count = Delivery.objects.filter(
            driver=availability.driver,
            status__in=['assigned', 'accepted', 'picked_up', 'en_route']
        ).count()
        
        # Driver is available if:
        # - They're marked as available, OR
        # - They have no active deliveries (safety check)
        if availability.is_available or active_delivery_count == 0:
            truly_available.append(availability)
    
    # Filter by distance
    nearby_drivers = []
    for availability in truly_available:
        # If driver has no location set, use a default large distance but still include them
        if availability.current_latitude and availability.current_longitude:
            distance = calculate_distance(
                restaurant_lat, restaurant_lon,
                availability.current_latitude, availability.current_longitude
            )
            if distance <= radius_km:
                nearby_drivers.append({
                    'driver': availability.driver,
                    'availability': availability,
                    'distance': distance
                })
        else:
            # Include drivers without location (they might be new) with a penalty distance
            nearby_drivers.append({
                'driver': availability.driver,
                'availability': availability,
                'distance': radius_km * 0.8  # Place them near the edge of radius
            })
    
    # Sort by rating (descending) and distance (ascending)
    nearby_drivers.sort(key=lambda x: (-x['availability'].average_rating, x['distance']))
    
    return nearby_drivers


def assign_delivery_to_driver(order_id):
    """
    Automatically assign a delivery to the best available driver.
    Returns the created Delivery object or None if no drivers available.
    """
    try:
        order = Order.objects.select_related('restaurant').get(id=order_id)
    except Order.DoesNotExist:
        return None
    
    # Check if delivery already exists with a driver assigned
    if hasattr(order, 'delivery') and order.delivery.driver:
        # Delivery already has a driver assigned
        return order.delivery
    
    # If delivery exists but has no driver, we'll update it
    # Otherwise we'll create a new one
    existing_delivery = getattr(order, 'delivery', None) if hasattr(order, 'delivery') else None
    
    # Get restaurant coordinates
    if not order.restaurant.latitude or not order.restaurant.longitude:
        # TODO: Geocode restaurant address if coordinates not set
        return None
    
    # Find available drivers
    nearby_drivers = find_available_drivers(
        order.restaurant.latitude,
        order.restaurant.longitude,
        radius_km=10  # Can be configured in settings
    )
    
    if not nearby_drivers:
        return None
    
    # Assign to the best driver (first in sorted list)
    best_driver = nearby_drivers[0]['driver']
    distance = nearby_drivers[0]['distance']
    
    # Update existing delivery or create new one
    if existing_delivery:
        # Update the existing delivery record
        delivery = existing_delivery
        delivery.driver = best_driver
        delivery.status = 'assigned'
        delivery.pickup_latitude = order.restaurant.latitude
        delivery.pickup_longitude = order.restaurant.longitude
        delivery.delivery_latitude = order.delivery_latitude
        delivery.delivery_longitude = order.delivery_longitude
        delivery.distance_km = distance
        delivery.assigned_at = timezone.now()
        delivery.save()
    else:
        # Create new delivery record
        delivery = Delivery.objects.create(
            order=order,
            driver=best_driver,
            status='assigned',
            pickup_latitude=order.restaurant.latitude,
            pickup_longitude=order.restaurant.longitude,
            delivery_latitude=order.delivery_latitude,
            delivery_longitude=order.delivery_longitude,
            distance_km=distance,
            assigned_at=timezone.now()
        )
    
    # NOTE: Don't mark driver as busy yet - wait for acceptance
    # Driver will be marked as busy when they accept the delivery
    
    # Update order status
    order.status = 'confirmed'
    order.save()
    
    # Notify driver about new assignment
    notify_driver_new_delivery(delivery)
    
    return delivery


def reassign_delivery(delivery_id):
    """Reassign a delivery to a different driver (if rejected or cancelled)."""
    try:
        delivery = Delivery.objects.get(id=delivery_id)
    except Delivery.DoesNotExist:
        return None
    
    # Mark previous driver as available again
    if delivery.driver:
        try:
            availability = DriverAvailability.objects.get(driver=delivery.driver)
            availability.is_available = True
            availability.save()
        except DriverAvailability.DoesNotExist:
            pass
    
    # Find new driver
    nearby_drivers = find_available_drivers(
        delivery.pickup_latitude,
        delivery.pickup_longitude
    )
    
    if not nearby_drivers:
        delivery.status = 'pending'
        delivery.driver = None
        delivery.save()
        return None
    
    # Assign to new driver
    new_driver = nearby_drivers[0]['driver']
    delivery.driver = new_driver
    delivery.status = 'assigned'
    delivery.assigned_at = timezone.now()
    delivery.save()
    
    # Notify new driver
    notify_driver_new_delivery(delivery)
    
    # NOTE: Don't mark new driver as busy yet - wait for acceptance
    # Driver will be marked as busy when they accept the delivery
    
    return delivery


def notify_driver_new_delivery(delivery):
    """Send notification to driver about new delivery assignment via WebSocket."""
    if not delivery.driver:
        return
        
    from core.utils.websocket_notifications import notify_driver_new_delivery as notify_helper
    notify_helper(delivery.driver, delivery)


def get_pending_deliveries():
    """Get all deliveries pending assignment."""
    return Delivery.objects.filter(
        status='pending',
        driver__isnull=True
    ).select_related('order', 'order__restaurant')
