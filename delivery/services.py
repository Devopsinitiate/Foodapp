import logging
from django.utils import timezone
from delivery.models import Delivery, DriverAvailability
from orders.models import Order
from delivery.assignment import assign_delivery_to_driver
from core.utils.websocket_notifications import notify_driver_new_delivery as notify_driver_ws
from utils.emails import send_driver_new_delivery_email, send_driver_assigned_email, send_email_async
from core.utils.websocket_notifications import notify_customer_order_status
from utils.emails import send_driver_assigned_email

logger = logging.getLogger(__name__)

def process_delivery_assignment(order_id, max_retries=3, current_retry=0):
    """
    Synchronous logic for assigning a delivery.
    Can be called by Celery task or directly as fallback.
    Returns dict with success/error status to help caller decide on retries.
    """
    logger.info(f"Processing delivery assignment for order {order_id} (Attempt {current_retry + 1}/{max_retries + 1})")
    
    try:
        # 1. Validate Order
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found")
            return {'success': False, 'error': 'Order not found', 'retry': False}
        
        # 2. Check Existing
        try:
            existing_delivery = Delivery.objects.get(order_id=order_id)
            if existing_delivery.driver and existing_delivery.status != 'pending':
                logger.info(f"✓ Delivery for order {order_id} already assigned to driver {existing_delivery.driver.id}")
                return {'success': True, 'delivery_id': existing_delivery.id, 'already_assigned': True}
        except Delivery.DoesNotExist:
            pass

        # 3. Check Overall Driver Availability
        online_drivers_count = DriverAvailability.objects.filter(
            is_online=True,
            driver__is_verified_driver=True,
            driver__is_active=True
        ).count()
        
        if online_drivers_count == 0:
            logger.warning(f"⚠ No online drivers available.")
            if current_retry >= max_retries:
                _mark_for_manual_assignment(order_id, 'No drivers online')
                return {'success': False, 'error': 'No drivers online', 'retry': False}
            return {'success': False, 'error': 'No drivers online', 'retry': True}

        # 4. Attempt Assignment
        delivery = assign_delivery_to_driver(order_id)
        
        if delivery and delivery.driver:
            # 5. Success - Send Notifications
            _send_assignment_notifications(delivery)
            return {'success': True, 'delivery_id': delivery.id, 'driver_id': delivery.driver.id}
        else:
            # 6. Failure - Drivers online but maybe busy/far
            logger.warning(f"⚠ No suitable drivers found for order {order_id}")
            if current_retry >= max_retries:
                _mark_for_manual_assignment(order_id, 'All drivers busy')
                return {'success': False, 'error': 'All drivers busy', 'retry': False}
            return {'success': False, 'error': 'All drivers busy', 'retry': True}

    except Exception as e:
        logger.error(f"Error in process_delivery_assignment: {e}", exc_info=True)
        return {'success': False, 'error': str(e), 'retry': True}

def process_driver_notification(delivery_id):
    """
    Synchronous logic to notify driver of new delivery.
    """
    try:
        delivery = Delivery.objects.select_related(
            'order', 'order__restaurant', 'order__user'
        ).get(id=delivery_id)
        
        # WebSocket
        notify_driver_ws(delivery.driver, delivery)
        
        # Email
        send_email_async(send_driver_new_delivery_email, delivery)
        send_email_async(send_driver_assigned_email, delivery.order, delivery)
        
        logger.info(f"Notifications sent to driver {delivery.driver.id} for delivery {delivery_id}")
        return {'success': True}
        
    except Delivery.DoesNotExist:
        logger.error(f"Delivery {delivery_id} not found")
        return {'success': False, 'error': 'Delivery not found'}
    except Exception as e:
        logger.error(f"Error sending driver notification: {e}")
        return {'success': False, 'error': str(e)}

# --- Helpers ---

def _mark_for_manual_assignment(order_id, reason):
    try:
        delivery_record, created = Delivery.objects.get_or_create(
            order_id=order_id,
            defaults={'status': 'pending', 'driver_notes': f'{reason} - requires manual assignment'}
        )
        if not created:
            delivery_record.status = 'pending'
            delivery_record.driver_notes = f'{reason} - requires manual assignment'
            delivery_record.save()
        logger.warning(f"Order {order_id} marked for manual assignment: {reason}")
    except Exception as e:
        logger.error(f"Error marking manual assignment: {e}")

def _send_assignment_notifications(delivery):
    # Driver Notification (Recursively call the service logic, but we can just do it direct/async)
    # Since we are inside the 'assignment' logic, we might want to schedule this or run it.
    # To avoid circularity if we used the task, we can call the service logic directly.
    # But usually we want this async too.
    # For simplicity, we'll just call the non-blocking helpers directly here.
    
    # WebSocket to Driver
    notify_driver_ws(delivery.driver, delivery)
    
    # WebSocket to Customer
    notify_customer_order_status(
        delivery.order,
        'driver_assigned',
        f'Driver {delivery.driver.get_full_name()} is on the way!'
    )
    
    # Email to Customer
    # send_email_async(send_driver_assigned_email, delivery.order, delivery) 
    # (This is already covered in the driver notification logic usually, let's check tasks.py)
    # tasks.py's assign_delivery_async called notify_driver_new_delivery.delay() AND notified customer.
    
    # For the fallback, we want to ensure everything happens.
    # We will trigger the driver notification logic separately if possible or just do it here.
    # Let's do it here to be safe and complete.
    
    # Email to Driver
    send_email_async(send_driver_new_delivery_email, delivery)
