"""
Celery tasks for async delivery processing.
"""
from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def assign_delivery_async(self, order_id):
    """
    Async task to assign delivery. Delegates to service logic.
    """
    from delivery.services import process_delivery_assignment
    
    result = process_delivery_assignment(order_id, max_retries=self.max_retries, current_retry=self.request.retries)
    
    if result['success']:
        return result
    
    if result.get('retry'):
        # Retry with exponential backoff
        countdown = 30 * (self.request.retries + 1)
        logger.info(f"⏳ Retrying assignment for order {order_id} in {countdown}s...")
        raise self.retry(countdown=countdown)
    
    return result

@shared_task
def notify_driver_new_delivery(driver_id, delivery_id):
    """
    Async task to notify driver. Delegates to service logic.
    """
    from delivery.services import process_driver_notification
    return process_driver_notification(delivery_id)


@shared_task
def check_assignment_timeout(delivery_id):
    """
    Check if driver hasaccepted delivery within timeout period.
    If not, reassign to another driver.
    """
    from delivery.models import Delivery
    from delivery.assignment import reassign_delivery
    from django.conf import settings
    
    try:
        delivery = Delivery.objects.get(id=delivery_id)
        
        # If still in 'assigned' status after timeout, reassign
        if delivery.status == 'assigned':
            timeout = getattr(settings, 'DELIVERY_ASSIGNMENT_TIMEOUT', 300)  # 5 minutes default
            time_since_assignment = (timezone.now() - delivery.assigned_at).total_seconds()
            
            if time_since_assignment >= timeout:
                logger.warning(f"Delivery {delivery_id} not accepted within timeout, reassigning...")
                
                # Notify original driver of reassignment (Non-blocking)
                if delivery.driver:
                    from core.utils.websocket_notifications import notify_driver_delivery_reassigned
                    notify_driver_delivery_reassigned(delivery.driver.id, delivery.id, 'Not accepted within time limit')
                
                # Reassign to next driver
                new_delivery = reassign_delivery(delivery_id)
                if new_delivery and new_delivery.driver:
                    from delivery.services import process_driver_notification
                    from core.utils.task_helper import run_task_safe
                    
                    # Use safe execution for the nested task
                    run_task_safe(notify_driver_new_delivery, process_driver_notification, new_delivery.id)
                    
                    return {'success': True, 'reassigned': True}
                else:
                    return {'success': True, 'reassigned': False, 'reason': 'No drivers available'}
        
        return {'success': True, 'action': 'none', 'status': delivery.status}
        
    except Delivery.DoesNotExist:
        logger.error(f"Delivery {delivery_id} not found for timeout check")
        return {'success': False, 'error': 'Delivery not found'}


@shared_task
def broadcast_location_update(delivery_id, latitude, longitude):
    """
    Broadcast driver location update to customer tracking page.
    """
    from delivery.models import Delivery
    
    try:
        delivery = Delivery.objects.get(id=delivery_id)
        order_id = delivery.order_id
        
        # Calculate ETA (simplified - can use Google Maps API for accuracy)
        eta_minutes = 15  # Placeholder
        
        # Send to customer tracking page (Non-blocking)
        from core.utils.websocket_notifications import notify_customer_driver_location
        notify_customer_driver_location(delivery.order, latitude, longitude, eta_minutes=15)
        
        return {'success': True}
        
    except Delivery.DoesNotExist:
        return {'success': False, 'error': 'Delivery not found'}


@shared_task
def notify_delivery_status_change(delivery_id, status, message):
    """
    Notify customer of delivery status change via WebSocket.
    """
    from delivery.models import Delivery
    
    try:
        delivery = Delivery.objects.get(id=delivery_id)
        order_id = delivery.order_id
        
        # Send notification (Non-blocking)
        from core.utils.websocket_notifications import notify_customer_order_status
        notify_customer_order_status(delivery.order, status, message)
        
        return {'success': True}
        
    except Delivery.DoesNotExist:
        return {'success': False, 'error': 'Delivery not found'}