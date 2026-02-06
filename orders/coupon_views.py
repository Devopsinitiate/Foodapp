"""
Coupon application views.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from decimal import Decimal

from .coupon_utils import apply_coupon_to_session, remove_coupon_from_session, get_applied_coupon
from .models import Cart


@login_required
@require_http_methods(["POST"])
def apply_coupon_view(request):
    """Apply coupon code to cart."""
    import json
    
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
    except:
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    if not code:
        return JsonResponse({'error': 'Please enter a coupon code'}, status=400)
    
    # Get user's cart
    try:
        cart = Cart.objects.get(user=request.user)
    except Cart.DoesNotExist:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    if not cart.cart_items.exists():
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # Get restaurant from first cart item (all items must be from same restaurant)
    first_item = cart.cart_items.select_related('menu_item__restaurant').first()
    restaurant = first_item.menu_item.restaurant if first_item else None
    
    if not restaurant:
        return JsonResponse({'error': 'Invalid cart state'}, status=400)
    
    # Get subtotal
    subtotal = cart.subtotal
    
    # Apply coupon
    result = apply_coupon_to_session(request, code, restaurant, subtotal)
    
    if not result['success']:
        return JsonResponse({'error': result['message']}, status=400)
    
    # Calculate new total
    delivery_fee = restaurant.delivery_fee if restaurant.delivery_fee else Decimal('5.00')
    tax = cart.get_tax() if hasattr(cart, 'get_tax') else (cart.subtotal * Decimal('0.08'))
    total = subtotal - result['discount'] + delivery_fee + tax
    
    return JsonResponse({
        'success': True,
        'message': result['message'],
        'discount': float(result['discount']),
        'coupon_code': code,
        'new_total': float(total),
        'subtotal': float(subtotal),
        'delivery_fee': float(delivery_fee),
        'tax': float(tax)
    })


@login_required
@require_http_methods(["POST"])
def remove_coupon_view(request):
    """Remove applied coupon."""
    remove_coupon_from_session(request)
    
    # Recalculate total
    try:
        cart = Cart.objects.get(user=request.user)
        subtotal = cart.subtotal
        
        # Get restaurant from first cart item
        first_item = cart.cart_items.select_related('menu_item__restaurant').first()
        restaurant = first_item.menu_item.restaurant if first_item else None
        
        delivery_fee = restaurant.delivery_fee if (restaurant and restaurant.delivery_fee) else Decimal('5.00')
        tax = cart.get_tax() if hasattr(cart, 'get_tax') else (subtotal * Decimal('0.08'))
        total = subtotal + delivery_fee + tax
        
        return JsonResponse({
            'success': True,
            'message': 'Coupon removed',
            'new_total': float(total),
            'subtotal': float(subtotal),
            'delivery_fee': float(delivery_fee),
            'tax': float(tax)
        })
    except Cart.DoesNotExist:
        return JsonResponse({
            'success': True,
            'message': 'Coupon removed'
        })
