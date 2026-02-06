"""
Notification dispatcher with Celery fallback support.
Intelligently routes notifications through Celery or database queue.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def celery_is_available():
    """
    Check if Celery is available and responsive.
    """
    # Check if Celery is enabled in settings
    if not getattr(settings, 'ENABLE_CELERY', True):
        logger.info("Celery is disabled in settings")
        return False
    
    try:
        # Try to import Celery
        from celery import current_app
        
        # Try to get Celery stats (quick check)
        inspect = current_app.control.inspect(timeout=1.0)
        stats = inspect.stats()
        
        if stats:
            logger.debug(f"Celery is available with {len(stats)} workers")
            return True
        else:
            logger.warning("Celery has no active workers")
            return False
            
    except Exception as e:
        logger.warning(f"Celery not available: {e}")
        return False


def dispatch_notification(notification_type, recipient, message_data, 
                          backend='email', priority=5, scheduled_for=None,
                         metadata=None):
    """
    Smart notification dispatcher.
    
    Tries to use Celery if available, otherwise queues in database.
    
    Args:
        notification_type: Type of notification ('order_created', 'email', etc.)
        recipient: Email address, phone number, or user ID
        message_data: Dict with message content
        backend: 'email', 'sms', 'whatsapp', or 'push'
        priority: 1-10 (lower = higher priority)
        scheduled_for: When to send (defaults to now)
        metadata: Additional context (order_id, etc.)
    
    Returns:
        dict: {'success': bool, 'method': str, 'message': str}
    """
    from core.models import NotificationQueue
    
    if scheduled_for is None:
        scheduled_for = timezone.now()
    
    if metadata is None:
        metadata = {}
    
    # If Celery is available, try to use it
    if celery_is_available():
        try:
            from core.tasks import send_notification_task
            
            # Dispatch to Celery
            result = send_notification_task.delay(
                notification_type=notification_type,
                recipient=recipient,
                message_data=message_data,
                backend=backend,
                metadata=metadata
            )
            
            logger.info(f"Notification dispatched to Celery: {result.id}")
            return {
                'success': True,
                'method': 'celery',
                'task_id': str(result.id),
                'message': 'Dispatched to Celery'
            }
            
        except Exception as e:
            logger.error(f"Failed to dispatch to Celery: {e}", exc_info=True)
            # Fall through to database queue
    
    # Fallback to database queue
    try:
        notification = NotificationQueue.objects.create(
            notification_type=notification_type,
            backend=backend,
            recipient=recipient,
            message_data=message_data,
            priority=priority,
            scheduled_for=scheduled_for,
            metadata=metadata,
            subject=message_data.get('subject', '')
        )
        
        logger.info(f"Notification queued in database: {notification.id}")
        
        # If synchronous fallback is enabled and notification is high priority
        if getattr(settings, 'FALLBACK_TO_SYNC', False) and priority <= 3:
            from core.utils.notification_sender import send_notification
            result = send_notification(notification)
            return {
                'success': result['success'],
                'method': 'sync',
                'notification_id': notification.id,
                'message': 'Sent synchronously'
            }
        
        return {
            'success': True,
            'method': 'queued',
            'notification_id': notification.id,
            'message': 'Queued in database'
        }
        
    except Exception as e:
        logger.error(f"Failed to queue notification: {e}", exc_info=True)
        return {
            'success': False,
            'method': 'failed',
            'message': str(e)
        }


def dispatch_email(subject, message, recipient, html_message=None, 
                   priority=5, metadata=None):
    """
    Convenience function for sending emails.
    
    Args:
        subject: Email subject
        message: Plain text message
        recipient: Email address
        html_message: HTML version (optional)
        priority: 1-10
        metadata: Additional context
    
    Returns:
        dict: Dispatch result
    """
    message_data = {
        'subject': subject,
        'message': message,
        'html_message': html_message or message,
        'from_email': settings.DEFAULT_FROM_EMAIL,
    }
    
    return dispatch_notification(
        notification_type='email',
        recipient=recipient,
        message_data=message_data,
        backend='email',
        priority=priority,
        metadata=metadata
    )


def dispatch_order_notification(order, notification_type='order_created'):
    """
    Dispatch order-related notification to restaurant owner.
    
    Args:
        order: Order instance
        notification_type: Type of notification
    
    Returns:
        dict: Dispatch result
    """
    restaurant = order.restaurant
    
    # Prepare message data
    message_data = {
        'order_id': order.id,
        'order_number': order.order_number,
        'customer_name': order.user.get_full_name() or order.user.username,
        'total': float(order.total),
        'items': [
            {
                'name': item.item_name,
                'quantity': item.quantity,
                'price': float(item.total_price)
            }
            for item in order.items.all()
        ],
        'delivery_address': order.delivery_address,
        'restaurant_name': restaurant.name,
    }
    
    # Send to restaurant owner's email
    recipient = restaurant.email
    
    return dispatch_notification(
        notification_type=notification_type,
        recipient=recipient,
        message_data=message_data,
        backend='email',
        priority=3,  # High priority
        metadata={'order_id': order.id, 'restaurant_id': restaurant.id}
    )
