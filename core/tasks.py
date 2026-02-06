"""
Celery tasks for core notifications.
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification_task(self, notification_type, recipient, message_data, 
                           backend='email', metadata=None):
    """
    Celery task to send notification.
    
    Args:
        notification_type: Type of notification
        recipient: Recipient address/ID
        message_data: Message content dict
        backend: Delivery backend
        metadata: Additional context
    
    Returns:
        dict: Result of send operation
    """
    from core.utils.notification_sender import send_notification
    from core.models import NotificationQueue
    
    try:
        # Create notification record
        notification = NotificationQueue.objects.create(
            notification_type=notification_type,
            backend=backend,
            recipient=recipient,
            message_data=message_data,
            metadata=metadata or {},
            subject=message_data.get('subject', ''),
            status='processing'
        )
        
        # Send notification
        result = send_notification(notification)
        
        if result['success']:
            logger.info(f"Notification {notification.id} sent successfully")
            return {'success': True, 'notification_id': notification.id}
        else:
            # Retry if failed
            if self.request.retries < self.max_retries:
                countdown = 60 * (2 ** self.request.retries)  # Exponential backoff
                raise self.retry(countdown=countdown)
            
            return {'success': False, 'notification_id': notification.id, 'error': result['message']}
            
    except Exception as exc:
        logger.error(f"Error in send_notification_task: {exc}", exc_info=True)
        
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        
        return {'success': False, 'error': str(exc)}


@shared_task
def process_notification_queue():
    """
    Process pending notifications in the queue.
    Run periodically (e.g., every 5 minutes) to handle fallback notifications.
    """
    from core.models import NotificationQueue
    from core.utils.notification_sender import send_notification
    
    # Get pending notifications that are due
    pending = NotificationQueue.objects.filter(
        status='pending',
        scheduled_for__lte=timezone.now()
    ).order_by('priority', 'scheduled_for')[:50]  # Process in batches
    
    results = {
        'processed': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for notification in pending:
        results['processed'] += 1
        
        # Check if should retry
        if not notification.should_retry():
            logger.warning(f"Skipping notification {notification.id} - max attempts reached")
            results['skipped'] += 1
            continue
        
        # Send notification
        result = send_notification(notification)
        
        if result['success']:
            results['sent'] += 1
        else:
            results['failed'] += 1
    
    logger.info(f"Queue processing complete: {results}")
    return results


@shared_task
def retry_failed_notifications():
    """
    Retry failed notifications that are eligible for retry.
    Run periodically to handle transient failures.
    """
    from core.models import NotificationQueue
    from core.utils.notification_sender import send_notification
    
    # Get failed notifications that should be retried
    failed = NotificationQueue.objects.filter(
        status='failed'
    ).order_by('last_error_at')[:20]  # Small batch
    
    results = {
        'retried': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0
    }
    
    for notification in failed:
        if not notification.should_retry():
            results['skipped'] += 1
            continue
        
        # Check if enough time has passed for retry (exponential backoff)
        if notification.last_error_at:
            retry_delay = notification.get_retry_delay()
            time_since_failure = (timezone.now() - notification.last_error_at).total_seconds()
            
            if time_since_failure < retry_delay:
                continue  # Not ready for retry yet
        
        # Reset to pending and retry
        notification.status = 'pending'
        notification.save(update_fields=['status'])
        
        results['retried'] += 1
        
        result = send_notification(notification)
        if result['success']:
            results['sent'] += 1
        else:
            results['failed'] += 1
    
    logger.info(f"Retry processing complete: {results}")
    return results


@shared_task
def cleanup_old_notifications(days=30):
    """
    Delete old sent notifications to keep database clean.
    Run once per day.
    """
    from core.models import NotificationQueue
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(days=days)
    
    deleted, _ = NotificationQueue.objects.filter(
        status='sent',
        sent_at__lt=cutoff
    ).delete()
    
    logger.info(f"Deleted {deleted} old notifications (older than {days} days)")
    return {'deleted': deleted}
