"""
Coupon validation and utility functions.
"""
from decimal import Decimal
from django.utils import timezone
from .models import Coupon, CouponUsage, Order


def validate_coupon(code, user, restaurant, subtotal):
    """
    Validate coupon and return discount amount or error.
    
    Args:
        code: Coupon code (str)
        user: User model instance
        restaurant: Restaurant model instance
        subtotal: Order subtotal (Decimal)
    
    Returns:
        tuple: (is_valid, discount_amount, error_message, coupon_obj)
    """
    # Convert subtotal to Decimal if needed
    if not isinstance(subtotal, Decimal):
        subtotal = Decimal(str(subtotal))
    
    # Try to get coupon (case-insensitive)
    try:
        coupon = Coupon.objects.get(code__iexact=code)
    except Coupon.DoesNotExist:
        return (False, Decimal('0'), "Invalid coupon code", None)
    
    # Check if active
    if not coupon.is_active:
        return (False, Decimal('0'), "This coupon is no longer active", None)
    
    # Check dates
    now = timezone.now()
    if now < coupon.valid_from:
        return (False, Decimal('0'), "This coupon is not yet valid", None)
    if now > coupon.valid_until:
        return (False, Decimal('0'), "This coupon has expired", None)
    
    # Check restaurant scope
    if coupon.scope == 'restaurant':
        if not coupon.restaurant or coupon.restaurant != restaurant:
            return (False, Decimal('0'), f"This coupon is only valid at {coupon.restaurant.name if coupon.restaurant else 'specific restaurants'}", None)
    
    # Check minimum order amount
    if subtotal < coupon.min_order_amount:
        return (False, Decimal('0'), f"Minimum order of ${coupon.min_order_amount} required for this coupon", None)
    
    # Check total usage limit
    if coupon.max_total_uses:
        total_uses = coupon.get_usage_count()
        if total_uses >= coupon.max_total_uses:
            return (False, Decimal('0'), "This coupon has reached its usage limit", None)
    
    # Check per-user usage limit
    user_uses = CouponUsage.objects.filter(coupon=coupon, user=user).count()
    if user_uses >= coupon.max_uses_per_user:
        return (False, Decimal('0'), "You have already used this coupon the maximum number of times", None)
    
    # Check first order only
    if coupon.first_order_only:
        has_completed_orders = Order.objects.filter(
            user=user, 
            status='delivered'
        ).exists()
        if has_completed_orders:
            return (False, Decimal('0'), "This coupon is only valid for first-time orders", None)
    
    # Calculate discount
    discount = coupon.calculate_discount(subtotal)
    
    return (True, discount, "", coupon)


def apply_coupon_to_session(request, code, restaurant, subtotal):
    """
    Apply coupon to user session.
    
    Returns:
        dict: {'success': bool, 'discount': Decimal, 'message': str, 'coupon': Coupon}
    """
    if not code:
        return {
            'success': False,
            'discount': Decimal('0'),
            'message': 'Please enter a coupon code',
            'coupon': None
        }
    
    # Validate coupon
    is_valid, discount, error, coupon = validate_coupon(
        code, request.user, restaurant, subtotal
    )
    
    if not is_valid:
        return {
            'success': False,
            'discount': Decimal('0'),
            'message': error,
            'coupon': None
        }
    
    # Store in session
    request.session['coupon_code'] = code
    request.session['discount'] = float(discount)
    request.session['coupon_id'] = coupon.id
    
    return {
        'success': True,
        'discount': discount,
        'message': f'Coupon applied! You saved ${discount:.2f}',
        'coupon': coupon
    }


def remove_coupon_from_session(request):
    """Remove coupon from session."""
    request.session.pop('coupon_code', None)
    request.session.pop('discount', None)
    request.session.pop('coupon_id', None)


def get_applied_coupon(request):
    """
    Get currently applied coupon from session.
    
    Returns:
        dict: {'code': str, 'discount': Decimal, 'coupon': Coupon or None}
    """
    code = request.session.get('coupon_code')
    discount = request.session.get('discount', 0)
    coupon_id = request.session.get('coupon_id')
    
    coupon = None
    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)
        except Coupon.DoesNotExist:
            # Coupon was deleted, clear session
            remove_coupon_from_session(request)
            return {'code': None, 'discount': Decimal('0'), 'coupon': None}
    
    return {
        'code': code,
        'discount': Decimal(str(discount)) if discount else Decimal('0'),
        'coupon': coupon
    }
