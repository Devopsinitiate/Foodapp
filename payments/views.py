"""
Payment processing views and webhook handlers for Paystack integration.
"""
import hmac
import hashlib
import json
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages

import requests

from orders.models import Order
from .models import Payment, PaymentWebhookLog


# ============ Payment Initialization ============

@login_required
@require_http_methods(["POST"])
def initialize_payment_view(request, order_id):
    """
    Initialize Paystack payment for an order.
    Returns authorization URL for payment.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    
    # Check if order is already paid
    if order.payment_status == 'paid':
        return JsonResponse({
            'error': 'Order already paid'
        }, status=400)
    
    # Create or get payment record
    payment, created = Payment.objects.get_or_create(
        order=order,
        user=request.user,
        defaults={
            'amount': order.total,
            'currency': 'NGN'
        }
    )
    
    # Prepare Paystack request
    url = 'https://api.paystack.co/transaction/initialize'
    
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    
    # Convert amount to kobo (Paystack uses smallest currency unit)
    amount_in_kobo = int(float(order.total) * 100)
    
    data = {
        'email': request.user.email,
        'amount': amount_in_kobo,
        'reference': payment.reference,
        'currency': 'NGN',
        'metadata': {
            'order_id': order.id,
            'order_number': order.order_number,
            'user_id': request.user.id,
            'customer_name': request.user.get_full_name() or request.user.username,
        },
        'callback_url': request.build_absolute_uri(f'/payments/verify/{payment.reference}/'),
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status'):
            # Update payment with Paystack details
            payment.paystack_reference = response_data['data']['reference']
            payment.paystack_access_code = response_data['data']['access_code']
            payment.authorization_url = response_data['data']['authorization_url']
            payment.status = 'processing'
            payment.save()
            
            return JsonResponse({
                'success': True,
                'authorization_url': payment.authorization_url,
                'access_code': payment.paystack_access_code,
                'reference': payment.reference
            })
        else:
            payment.mark_as_failed(response_data.get('message', 'Payment initialization failed'))
            return JsonResponse({
                'error': response_data.get('message', 'Payment initialization failed')
            }, status=400)
            
    except Exception as e:
        payment.mark_as_failed(str(e))
        return JsonResponse({
            'error': f'Payment initialization error: {str(e)}'
        }, status=500)


# ============ Payment Verification ============

@login_required
def verify_payment_view(request, reference):
    """
    Verify payment status after user completes payment.
    This is called by Paystack redirect after payment.
    """
    # Try to find payment by reference (local or Paystack)
    payment = None
    
    # Try local reference first
    try:
        payment = Payment.objects.get(reference=reference, user=request.user)
    except Payment.DoesNotExist:
        # Try Paystack reference as fallback
        try:
            payment = Payment.objects.get(paystack_reference=reference, user=request.user)
        except Payment.DoesNotExist:
            messages.error(request, 'Payment not found. Please contact support.')
            return redirect('checkout')
    
    # Log verification attempt
    print(f"Verifying payment: {payment.reference} (Paystack ref: {payment.paystack_reference})")
    
    # If already successful, just redirect (idempotency)
    if payment.status == 'success':
        # Double check order payment status is synced
        if payment.order.payment_status != 'paid':
            print(f"🔄 Syncing order payment status for {payment.order.order_number}: {payment.order.payment_status} -> paid")
            payment.order.payment_status = 'paid'
            payment.order.save(update_fields=['payment_status'])
            print(f"✅ Order {payment.order.order_number} payment_status synced: {payment.order.payment_status}")
        
        messages.info(request, f'Payment already verified for Order #{payment.order.order_number}')
        return redirect('orders:tracking', order_number=payment.order.order_number)
    
    # Verify with Paystack
    url = f'https://api.paystack.co/transaction/verify/{reference}'
    
    headers = {
        'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
    }
    
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status'):
            data = response_data['data']
            
            if data['status'] == 'success':
                # Payment successful - mark it
                print(f'🔄 Verifying payment: {payment.reference}, current order payment_status: {payment.order.payment_status}')
                payment.mark_as_success(data)
                print(f'✅ Verification processed for payment: {payment.reference}, updated order payment_status: {payment.order.payment_status}')
                
                print(f"✅ Payment verified: {payment.reference} for Order #{payment.order.order_number}")
                print(f"📋 Order payment_status: {payment.order.payment_status}")
                
                messages.success(
                    request,
                    f'Payment successful! Order #{payment.order.order_number} confirmed.'
                )
                return redirect('orders:tracking', order_number=payment.order.order_number)
            else:
                # Payment failed
                payment.mark_as_failed(data.get('gateway_response', 'Payment failed'))
                
                print(f"❌ Payment failed: {payment.reference} - {data.get('gateway_response')}")
                
                messages.error(request, 'Payment failed. Please try again.')
                return redirect('checkout')
        else:
            # Could not verify
            error_msg = response_data.get('message', 'Could not verify payment')
            print(f"⚠️ Payment verification failed: {payment.reference} - {error_msg}")
            
            messages.error(request, 'Could not verify payment. Please contact support.')
            return redirect('checkout')
            
    except Exception as e:
        print(f"🔥 Payment verification error: {payment.reference} - {str(e)}")
        import traceback
        traceback.print_exc()
        
        messages.error(request, f'Payment verification error: {str(e)}')
        return redirect('checkout')



# ============ Webhook Handler ============

@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook(request):
    """
    Handle Paystack webhook events.
    This endpoint receives real-time payment notifications from Paystack.
    """
    # Get request data
    payload = request.body
    signature = request.headers.get('X-Paystack-Signature', '')
    
    # Get client IP
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip_address:
        ip_address = ip_address.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR')
    
    # Verify webhook signature
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    signature_valid = hmac.compare_digest(computed_signature, signature)
    
    # Verify IP address (Paystack IPs)
    paystack_ips = getattr(settings, 'PAYSTACK_WEBHOOK_IPS', [])
    ip_valid = ip_address in paystack_ips if paystack_ips else True  # Skip IP check if not configured
    
    # Parse payload
    try:
        data = json.loads(payload)
        event = data.get('event')
        event_data = data.get('data', {})
    except json.JSONDecodeError:
        return HttpResponse('Invalid JSON', status=400)
    
    # Log webhook event
    webhook_log = PaymentWebhookLog.objects.create(
        event=event,
        payload=data,
        ip_address=ip_address,
        signature=signature,
        signature_valid=signature_valid
    )
    
    # Verify signature (IP check is optional in development)
    if not signature_valid:
        # In development, we might skip signature verification
        if not settings.DEBUG:
            webhook_log.mark_as_processed(error='Invalid signature')
            return HttpResponse('Invalid signature', status=400)
        else:
            # Log warning but continue in debug mode
            print(f'⚠️ Warning: Webhook signature invalid (DEBUG mode - continuing anyway)')
    
    # Process webhook event
    try:
        process_webhook_event(event, event_data, webhook_log)
        webhook_log.mark_as_processed()
        return HttpResponse('Webhook processed', status=200)
    except Exception as e:
        webhook_log.mark_as_processed(error=str(e))
        return HttpResponse(f'Error: {str(e)}', status=500)


def process_webhook_event(event, data, webhook_log):
    """
    Process different webhook events.
    """
    reference = data.get('reference')
    
    if not reference:
        return
    
    # Handle different events
    if event == 'charge.success':
        handle_charge_success(data, webhook_log)
    
    elif event == 'charge.failed':
        handle_charge_failed(data, webhook_log)
    
    elif event == 'transfer.success':
        # Handle transfer success (for vendor payouts)
        pass
    
    elif event == 'transfer.failed':
        # Handle transfer failure
        pass


def handle_charge_success(data, webhook_log):
    """
    Handle successful charge webhook.
    """
    reference = data.get('reference')
    
    try:
        # Try to find payment by Paystack reference first
        payment = None
        try:
            payment = Payment.objects.get(paystack_reference=reference)
        except Payment.DoesNotExist:
            # Fallback: Try local reference
            try:
                payment = Payment.objects.get(reference=reference)
            except Payment.DoesNotExist:
                print(f"⚠️ Webhook: Payment not found for reference {reference}")
                return
        
        webhook_log.payment = payment
        webhook_log.save()
        
        print(f"📥 Webhook received for payment: {payment.reference}")
        
        # Check if already processed (idempotency)
        if payment.status == 'success':
            print(f"✅ Payment already marked as success: {payment.reference}")
            # Even if already successful, ensure order status is correct
            if payment.order.payment_status != 'paid':
                print(f"🔄 Fixing order payment status for order {payment.order.order_number}: {payment.order.payment_status} -> paid")
                payment.order.payment_status = 'paid'
                payment.order.save(update_fields=['payment_status'])
                print(f"✅ Order {payment.order.order_number} payment_status fixed: {payment.order.payment_status}")
            return
        
        # Mark payment as successful (this also updates order status)
        print(f'🔄 Processing webhook for payment: {payment.reference}, current order payment_status: {payment.order.payment_status}')
        payment.mark_as_success(data)
        print(f'✅ Webhook processed for payment: {payment.reference}, updated order payment_status: {payment.order.payment_status}')
        
        print(f"✅ Payment marked as successful via webhook: {payment.reference}")
        print(f"📋 Order {payment.order.order_number} payment_status: {payment.order.payment_status}")
        
        # Send confirmation email (async with Celery in production)
        send_order_confirmation_email(payment.order)
        
        # Notify vendor (via WebSocket or push notification)
        notify_vendor_new_order(payment.order)
        
    except Exception as e:
        print(f"🔥 Error processing charge success webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise to mark webhook as failed



def handle_charge_failed(data, webhook_log):
    """
    Handle failed charge webhook.
    """
    reference = data.get('reference')
    
    try:
        payment = Payment.objects.get(paystack_reference=reference)
        webhook_log.payment = payment
        webhook_log.save()
        
        # Mark payment as failed
        error_message = data.get('gateway_response', 'Payment failed')
        payment.mark_as_failed(error_message)
        
        # Send failure notification
        send_payment_failure_email(payment.user, payment.order)
        
    except Payment.DoesNotExist:
        pass


# ============ Helper Functions ============

def send_order_confirmation_email(order):
    """
    Send order confirmation email to customer.
    In production, use Celery for async processing.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    subject = f'Order Confirmation - {order.order_number}'
    
    html_message = render_to_string('emails/order_confirmation.html', {
        'order': order,
        'user': order.user,
    })
    
    try:
        send_mail(
            subject,
            '',  # Plain text version
            settings.DEFAULT_FROM_EMAIL,
            [order.contact_email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception as e:
        print(f'Error sending email: {e}')


def send_payment_failure_email(user, order):
    """
    Send payment failure notification.
    """
    from django.core.mail import send_mail
    
    subject = f'Payment Failed - Order {order.order_number}'
    message = f'''
    Dear {user.get_full_name() or user.username},
    
    Your payment for order {order.order_number} could not be processed.
    
    Please try again or contact support if the issue persists.
    
    Thank you,
    FoodApp Team
    '''
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f'Error sending email: {e}')


def notify_vendor_new_order(order):
    """
    Notify vendor of new order via WebSocket or push notification.
    In production, use Django Channels for real-time notifications.
    """
    # TODO: Implement WebSocket notification
    pass


# ============ Saved Cards (Optional Feature) ============

@login_required
def get_saved_cards(request):
    """
    Get user's saved payment methods.
    """
    from .models import SavedCard
    
    cards = SavedCard.objects.filter(
        user=request.user,
        is_active=True
    ).exclude(exp_year__lt='2024')  # Filter expired cards
    
    cards_data = [{
        'id': card.id,
        'card_type': card.card_type,
        'last4': card.card_last4,
        'exp_month': card.exp_month,
        'exp_year': card.exp_year,
        'brand': card.brand,
        'is_default': card.is_default,
    } for card in cards]
    
    return JsonResponse({'cards': cards_data})