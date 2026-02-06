"""
Vendor coupon management views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta

from orders.models import Coupon, CouponUsage
from .models import Restaurant
from .forms import VendorCouponForm


def vendor_required(view_func):
    """Decorator to require vendor user type."""
    from functools import wraps
    
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access vendor dashboard.')
            return redirect('users:login')
        if request.user.user_type != 'vendor':
            messages.error(request, 'Access denied. Vendors only.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@vendor_required
def vendor_coupons_list(request):
    """List all coupons for vendor's restaurant."""
    # Get vendor's restaurant
    restaurant = request.user.restaurants.first()
    
    if not restaurant:
        messages.error(request, 'No restaurant found for your account.')
        return redirect('restaurants:vendor_dashboard')
    
    # Get all coupons for this restaurant
    coupons = Coupon.objects.filter(
        restaurant=restaurant
    ).annotate(
        usage_count=Count('usages'),
        total_discount=Sum('usages__discount_amount')
    ).order_by('-created_at')
    
    # Calculate stats
    active_coupons = coupons.filter(is_active=True, valid_until__gte=timezone.now()).count()
    total_redemptions = sum(c.usage_count for c in coupons)
    total_discount_given = sum(c.total_discount or 0 for c in coupons)
    
    context = {
        'restaurant': restaurant,
        'coupons': coupons,
        'active_coupons': active_coupons,
        'total_redemptions': total_redemptions,
        'total_discount_given': total_discount_given,
    }
    
    return render(request, 'restaurants/vendor/coupons.html', context)


@login_required
@vendor_required
def create_coupon(request):
    """Create a new restaurant-specific coupon."""
    restaurant = request.user.restaurants.first()
    
    if not restaurant:
        messages.error(request, 'No restaurant found for your account.')
        return redirect('restaurants:vendor_dashboard')
    
    if request.method == 'POST':
        form = VendorCouponForm(request.POST, restaurant=restaurant)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.scope = 'restaurant'
            coupon.restaurant = restaurant
            coupon.created_by = request.user
            coupon.save()
            
            messages.success(request, f'Coupon "{coupon.code}" created successfully!')
            return redirect('restaurants:vendor_coupons')
    else:
        form = VendorCouponForm(restaurant=restaurant)
    
    context = {
        'restaurant': restaurant,
        'form': form,
        'action': 'Create',
    }
    
    return render(request, 'restaurants/vendor/coupon_form.html', context)


@login_required
@vendor_required
def edit_coupon(request, pk):
    """Edit an existing coupon."""
    restaurant = request.user.restaurants.first()
    
    if not restaurant:
        messages.error(request, 'No restaurant found for your account.')
        return redirect('restaurants:vendor_dashboard')
    
    # Ensure coupon belongs to this vendor's restaurant
    coupon = get_object_or_404(Coupon, pk=pk, restaurant=restaurant)
    
    if request.method == 'POST':
        form = VendorCouponForm(request.POST, instance=coupon, restaurant=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, f'Coupon "{coupon.code}" updated successfully!')
            return redirect('restaurants:vendor_coupons')
    else:
        form = VendorCouponForm(instance=coupon, restaurant=restaurant)
    
    context = {
        'restaurant': restaurant,
        'form': form,
        'coupon': coupon,
        'action': 'Edit',
    }
    
    return render(request, 'restaurants/vendor/coupon_form.html', context)


@login_required
@vendor_required
def toggle_coupon(request, pk):
    """Toggle coupon active status."""
    restaurant = request.user.restaurants.first()
    
    if not restaurant:
        messages.error(request, 'No restaurant found.')
        return redirect('restaurants:vendor_dashboard')
    
    coupon = get_object_or_404(Coupon, pk=pk, restaurant=restaurant)
    
    if request.method == 'POST':
        coupon.is_active = not coupon.is_active
        coupon.save(update_fields=['is_active'])
        
        status = 'activated' if coupon.is_active else 'deactivated'
        messages.success(request, f'Coupon "{coupon.code}" {status}!')
    
    return redirect('restaurants:vendor_coupons')


@login_required
@vendor_required
def coupon_analytics(request, pk):
    """View detailed analytics for a coupon."""
    restaurant = request.user.restaurants.first()
    
    if not restaurant:
        messages.error(request, 'No restaurant found.')
        return redirect('restaurants:vendor_dashboard')
    
    coupon = get_object_or_404(
        Coupon.objects.annotate(
            usage_count=Count('usages'),
            total_discount=Sum('usages__discount_amount'),
            unique_users=Count('usages__user', distinct=True)
        ),
        pk=pk,
        restaurant=restaurant
    )
    
    # Get usage history
    usages = CouponUsage.objects.filter(
        coupon=coupon
    ).select_related('user', 'order').order_by('-used_at')[:50]
    
    # Calculate date-based stats (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_usages = CouponUsage.objects.filter(
        coupon=coupon,
        used_at__gte=thirty_days_ago
    )
    
    # Group by date for chart
    daily_usage = {}
    for usage in recent_usages:
        date_key = usage.used_at.date()
        if date_key not in daily_usage:
            daily_usage[date_key] = {'count': 0, 'discount': 0}
        daily_usage[date_key]['count'] += 1
        daily_usage[date_key]['discount'] += float(usage.discount_amount)
    
    # Average order value with coupon
    avg_order_value = recent_usages.aggregate(
        avg=Sum('order__total')
    )['avg'] or 0
    
    context = {
        'restaurant': restaurant,
        'coupon': coupon,
        'usages': usages,
        'daily_usage': dict(sorted(daily_usage.items())),
        'avg_order_value': avg_order_value / recent_usages.count() if recent_usages.count() > 0 else 0,
        'recent_count': recent_usages.count(),
    }
    
    return render(request, 'restaurants/vendor/coupon_analytics.html', context)
