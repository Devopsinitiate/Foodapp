"""
WebSocket notification utilities for easy real-time messaging.
Centralized functions for sending WebSocket notifications to different user types.
"""
import time
import logging
import threading
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def _send_websocket_message(group_name, message_data):
    """
    Internal helper to send WebSocket message with timing and error handling.
    """
    start_time = time.time()
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning(f"No channel layer configured. Skipping message to {group_name}")
            return False
            
        async_to_sync(channel_layer.group_send)(group_name, message_data)
        
        duration = time.time() - start_time
        if duration > 0.5:  # Log slow sends
            logger.warning(f"Slow WebSocket send to {group_name}: {duration:.2f}s")
        else:
            logger.debug(f"Sent WebSocket message to {group_name} in {duration:.3f}s")
        return True
    except Exception as e:
        error_msg = str(e)
        if "10054" in error_msg or "forcibly closed" in error_msg.lower():
            logger.error(f"Redis connection lost (10054) while sending to {group_name}. This is usually transient or means Redis is overloaded.")
        else:
            logger.error(f"Failed to send WebSocket message to {group_name}: {e}")
        return False


def _fire_and_forget_notification(group_name, message_data):
    """
    Send notification in a separate thread if Celery is disabled to avoid blocking.
    """
    if getattr(settings, 'ENABLE_CELERY', True):
        # If Celery is enabled, we usually call a task, 
        # but if we're here, we're doing it synchronously.
        # Still, we'll do it in a thread if it's potentially slow.
        threading.Thread(target=_send_websocket_message, args=(group_name, message_data), daemon=True).start()
    else:
        # If Celery is disabled, definitely use a thread to prevent timeouts in the view
        threading.Thread(target=_send_websocket_message, args=(group_name, message_data), daemon=True).start()


def notify_customer_order_status(order, status, message):
    """
    Notify customer about order status change via WebSocket.
    """
    data = {
        'type': 'delivery_status',
        'status': status,
        'message': message,
        'timestamp': timezone.now().isoformat()
    }
    _fire_and_forget_notification(f"order_{order.id}", data)
    
    # Send alias event for older frontend code
    alias_data = data.copy()
    alias_data['type'] = 'order_update'
    _fire_and_forget_notification(f"order_{order.id}", alias_data)
    
    return True


def notify_vendor_new_order(order):
    """
    Notify vendor about new order via WebSocket.
    """
    restaurant = order.restaurant
    data = {
        'type': 'new_order',
        'order_id': order.id,
        'order_number': order.order_number,
        'customer_name': order.user.get_full_name() or order.user.username,
        'total': float(order.total),
        'items_count': order.items.count(),
        'delivery_address': order.delivery_address,
        'created_at': order.created_at.isoformat(),
    }
    
    # Notify restaurant group
    _fire_and_forget_notification(f"restaurant_{restaurant.id}", data)
    
    # Also notify vendor personally
    _fire_and_forget_notification(f"vendor_{restaurant.owner.id}", data)
    
    return True


def notify_vendor_order_update(order, message):
    """
    Notify vendor about order update via WebSocket.
    """
    restaurant = order.restaurant
    data = {
        'type': 'order_status_update',
        'order_id': order.id,
        'status': order.status,
        'message': message
    }
    _fire_and_forget_notification(f"restaurant_{restaurant.id}", data)
    return True


def notify_driver_new_delivery(driver, delivery):
    """
    Notify driver about new delivery assignment via WebSocket.
    """
    from decimal import Decimal
    order = delivery.order
    
    # Get order items
    items = [
        {
            'name': item.item_name,
            'quantity': item.quantity,
            'price': float(item.total_price)
        }
        for item in order.items.all()
    ]
    
    data = {
        'type': 'new_delivery',
        'delivery_id': delivery.id,
        'order_number': order.order_number,
        'restaurant': order.restaurant.name,
        'distance': float(delivery.distance_km) if delivery.distance_km else 0,
        'earnings': float(order.total * Decimal('0.15')),  # 15% commission
        'pickup_address': order.restaurant.street_address or order.restaurant.name,
        'delivery_address': order.delivery_address,
        'customer_name': order.user.get_full_name() or order.user.username,
        'items': items,
        'total': float(order.total),
    }
    
    _fire_and_forget_notification(f"driver_{driver.id}", data)
    return True


def notify_driver_delivery_update(driver, delivery, status, message):
    """
    Notify driver about delivery status update.
    """
    data = {
        'type': 'status_update',
        'delivery_id': delivery.id,
        'status': status,
        'message': message
    }
    _fire_and_forget_notification(f"driver_{driver.id}", data)
    return True


def notify_driver_order_ready(driver_id, order):
    """
    Notify driver that an order is ready for pickup.
    """
    data = {
        'type': 'order_ready',
        'order_id': order.id,
        'order_number': order.order_number,
        'restaurant_name': order.restaurant.name,
    }
    _fire_and_forget_notification(f"driver_{driver_id}", data)
    return True


def notify_customer_driver_location(order, latitude, longitude, eta_minutes=None):
    """
    Notify customer about driver's real-time location.
    """
    data = {
        'type': 'location_update',
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': timezone.now().isoformat(),
        'eta_minutes': eta_minutes
    }
    _fire_and_forget_notification(f"order_{order.id}", data)
    return True


def notify_order_participants(order, event_type, data):
    """
    Notify all participants (customer, vendor, driver) about an order event.
    """
    # Notify customer
    notify_customer_order_status(order, data.get('status', 'update'), data.get('message', ''))
    
    # Notify vendor
    notify_vendor_order_update(order, data.get('message', ''))
    
    # Notify driver if assigned
    if hasattr(order, 'delivery') and order.delivery and order.delivery.driver:
        notify_driver_delivery_update(
            order.delivery.driver,
            order.delivery,
            data.get('status', ''),
            data.get('message', '')
        )
    
    return True
