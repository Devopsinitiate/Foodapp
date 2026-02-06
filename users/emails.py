import threading
import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email_async(email_func, *args, **kwargs):
    """
    Run email sending function in a background thread to prevent blocking.
    """
    thread = threading.Thread(
        target=email_func,
        args=args,
        kwargs=kwargs,
        daemon=True
    )
    thread.start()
    logger.debug(f"Started background thread for email: {email_func.__name__}")
    return True


def send_welcome_email(user):
    """Send welcome email to new users."""
    subject = 'Welcome to EmpressDish! 🍽️'
    
    # Get site URL from settings or use default
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/welcome.html', {
        'user': user,
        'site_name': 'EmpressDish',
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False


def send_order_confirmation_email(order):
    """Send order confirmation email to customer."""
    subject = f'Order Confirmation - #{order.order_number}'
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/order_confirmation.html', {
        'order': order,
        'user': order.user,
        'restaurant': order.restaurant,
        'items': order.items.all(),
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending order confirmation email: {e}")
        return False


def send_order_status_email(order):
    """Send order status update email to customer."""
    status_messages = {
        'confirmed': 'Your order has been confirmed!',
        'preparing': 'Your order is being prepared',
        'ready': 'Your order is ready for pickup',
        'out_for_delivery': 'Your order is out for delivery',
        'delivered': 'Your order has been delivered',
        'cancelled': 'Your order has been cancelled',
    }
    
    subject = f'Order Update - #{order.order_number}: {status_messages.get(order.status, "Status Updated")}'
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/order_status.html', {
        'order': order,
        'user': order.user,
        'status_message': status_messages.get(order.status, 'Your order status has been updated'),
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending order status email: {e}")
        return False


def send_new_order_notification_to_vendor(order):
    """Send new order notification to vendor."""
    subject = f'New Order Received - #{order.order_number}'
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/vendor_new_order.html', {
        'order': order,
        'vendor': order.restaurant.owner,
        'restaurant': order.restaurant,
        'items': order.items.all(),
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.restaurant.owner.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending vendor notification email: {e}")
        return False


def send_vendor_approval_email(vendor_profile):
    """Send approval email to vendor."""
    subject = 'Your Vendor Application Has Been Approved! 🎉'
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/vendor_approved.html', {
        'vendor': vendor_profile.user,
        'business_name': vendor_profile.business_name,
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[vendor_profile.user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending vendor approval email: {e}")
        return False


def send_vendor_rejection_email(vendor_profile):
    """Send rejection email to vendor."""
    subject = 'Update on Your Vendor Application'
    
    html_content = render_to_string('emails/vendor_rejected.html', {
        'vendor': vendor_profile.user,
        'business_name': vendor_profile.business_name,
        'reason': vendor_profile.rejection_reason,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[vendor_profile.user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending vendor rejection email: {e}")
        return False


def send_order_cancellation_email(order):
    """Send order cancellation email to customer."""
    subject = f'Order Cancelled - #{order.order_number}'
    
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    html_content = render_to_string('emails/order_cancelled.html', {
        'order': order,
        'user': order.user,
        'site_url': site_url,
    })
    text_content = strip_tags(html_content)
    
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.user.email]
    )
    email.attach_alternative(html_content, "text/html")
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending cancellation email: {e}")
        return False
