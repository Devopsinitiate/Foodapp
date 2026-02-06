"""
Notification sender - handles actual sending of notifications.
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def send_notification(notification):
    """
    Send a notification based on its backend type.
    
    Args:
        notification: NotificationQueue instance
    
    Returns:
        dict: {'success': bool, 'message': str}
    """
    notification.mark_processing()
    
    try:
        if notification.backend == 'email':
            result = send_email_notification(notification)
        elif notification.backend == 'sms':
            result = send_sms_notification(notification)
        elif notification.backend == 'whatsapp':
            result = send_whatsapp_notification(notification)
        elif notification.backend == 'push':
            result = send_push_notification(notification)
        else:
            raise ValueError(f"Unknown backend: {notification.backend}")
        
        if result['success']:
            notification.mark_sent()
        else:
           notification.mark_failed(result['message'])
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error sending notification {notification.id}: {error_msg}", exc_info=True)
        notification.mark_failed(error_msg)
        return {'success': False, 'message': error_msg}


def send_email_notification(notification):
    """Send email notification."""
    try:
        message_data = notification.message_data
        
        subject = message_data.get('subject', notification.subject)
        message = message_data.get('message', '')
        html_message = message_data.get('html_message')
        from_email = message_data.get('from_email', settings.DEFAULT_FROM_EMAIL)
        
        if html_message:
            # Use EmailMultiAlternatives for HTML email
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email,
                to=[notification.recipient]
            )
            email.attach_alternative(html_message, "text/html")
            email.send()
        else:
            # Simple text email
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[notification.recipient],
                fail_silently=False
            )
        
        logger.info(f"Email sent to {notification.recipient}")
        return {'success': True, 'message': 'Email sent'}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}


def send_sms_notification(notification):
    """Send SMS notification (placeholder for future implementation)."""
    logger.warning(f"SMS backend not implemented for notification {notification.id}")
    return {'success': False, 'message': 'SMS backend not implemented'}


def send_whatsapp_notification(notification):
    """Send WhatsApp notification (placeholder for future implementation)."""
    logger.warning(f"WhatsApp backend not implemented for notification {notification.id}")
    return {'success': False, 'message': 'WhatsApp backend not implemented'}


def send_push_notification(notification):
    """Send push notification (placeholder for future implementation)."""
    logger.warning(f"Push backend not implemented for notification {notification.id}")
    return {'success': False, 'message': 'Push backend not implemented'}
