from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging
import threading

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

def send_html_email(subject, template_name, context, recipient_list):
    """
    Send an HTML email using a template.
    """
    try:
        # Add site_url to context if not present
        if 'site_url' not in context:
            context['site_url'] = getattr(settings, 'SITE_URL', 'http://localhost:8000')

        html_message = render_to_string(template_name, context)
        plain_message = strip_tags(html_message)
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email '{subject}' sent to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email '{subject}' to {recipient_list}: {str(e)}")
        return False

def send_welcome_email(user):
    """Send welcome email to new user."""
    return send_html_email(
        subject="Welcome to EmpressDish! 🍽️",
        template_name="emails/welcome.html",
        context={'user': user},
        recipient_list=[user.email]
    )

def send_order_confirmation(order):
    """Send order confirmation email."""
    return send_html_email(
        subject=f"Order Confirmation #{order.order_number}",
        template_name="emails/order_confirmation.html",
        context={'order': order, 'user': order.user},
        recipient_list=[order.user.email]
    )

def send_order_cancellation_email(order):
    """Send order cancellation email."""
    return send_html_email(
        subject=f"Order Cancelled #{order.order_number}",
        template_name="emails/order_cancellation.html",
        context={'order': order, 'user': order.user},
        recipient_list=[order.user.email]
    )


def send_vendor_new_order(order):
    """Send new order notification to vendor."""
    try:
        vendor_email = order.restaurant.owner.email
        return send_html_email(
            subject=f"🔔 New Order #{order.order_number} - {order.restaurant.name}",
            template_name="emails/vendor_new_order.html",
            context={'order': order, 'vendor': order.restaurant.owner},
            recipient_list=[vendor_email]
        )
    except Exception as e:
        logger.error(f"Failed to send vendor new order email: {str(e)}")
        return False


def send_order_confirmed_email(order):
    """Send order confirmed notification to customer."""
    return send_html_email(
        subject=f"✅ Order Confirmed #{order.order_number}",
        template_name="emails/order_confirmed.html",
        context={'order': order, 'user': order.user},
        recipient_list=[order.user.email]
    )


def send_driver_assigned_email(order, delivery):
    """Send driver assigned notification to customer."""
    return send_html_email(
        subject=f"🚗 Driver Assigned to Order #{order.order_number}",
        template_name="emails/driver_assigned.html",
        context={'order': order, 'delivery': delivery, 'user': order.user},
        recipient_list=[order.user.email]
    )


def send_out_for_delivery_email(order, delivery=None):
    """Send out for delivery notification to customer."""
    context = {'order': order, 'user': order.user}
    if delivery:
        context['delivery'] = delivery
    
    return send_html_email(
        subject=f"🚚 Order #{order.order_number} is On the Way!",
        template_name="emails/out_for_delivery.html",
        context=context,
        recipient_list=[order.user.email]
    )


def send_order_delivered_email(order):
    """Send order delivered notification to customer."""
    return send_html_email(
        subject=f"✅ Order #{order.order_number} Delivered!",
        template_name="emails/order_delivered.html",
        context={'order': order, 'user': order.user},
        recipient_list=[order.user.email]
    )


def send_driver_new_delivery_email(delivery):
    """Send new delivery assignment to driver."""
    try:
        driver_email = delivery.driver.email
        return send_html_email(
            subject=f"🔔 New Delivery Assignment - Order #{delivery.order.order_number}",
            template_name="emails/driver_order_assigned.html",
            context={'delivery': delivery, 'driver': delivery.driver},
            recipient_list=[driver_email]
        )
    except Exception as e:
        logger.error(f"Failed to send driver new delivery email: {str(e)}")
        return False

