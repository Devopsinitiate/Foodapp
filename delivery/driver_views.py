"""
Driver Dashboard Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from datetime import timedelta, datetime
from django.core.paginator import Paginator
from functools import wraps

from users.models import User
from orders.models import Order
from .models import Delivery


def driver_required(view_func):
    """Decorator to require driver user type"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access driver dashboard.')
            return redirect('users:login')
        if request.user.user_type != 'driver':
            messages.error(request, 'Access denied. Drivers only.')
            return redirect('home')
        if not request.user.is_verified_driver:
            messages.warning(request, 'Your driver account is pending verification.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@driver_required
def driver_dashboard(request):
    """
    Main driver dashboard with earnings, active delivery, and available deliveries.
    """
    driver = request.user
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    # Today's deliveries and earnings
    today_deliveries = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__date=today
    )
    today_earnings = today_deliveries.aggregate(
        total=Sum('order__delivery_fee')
    )['total'] or 0
    today_count = today_deliveries.count()
    
    # Week earnings
    week_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=week_ago
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    # Month earnings
    month_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=month_start
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    # Active delivery (current delivery in progress)
    active_delivery = Delivery.objects.filter(
        driver=driver,
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).select_related('order__restaurant', 'order__user').first()
    
    # Available deliveries (pending assignment or newly assigned to this driver)
    # Show pending deliveries without a driver OR deliveries assigned to this driver that aren't accepted yet
    available_deliveries = Delivery.objects.filter(
        Q(status='pending', driver__isnull=True) |
        Q(status='assigned', driver=driver)
    ).select_related('order__restaurant', 'order__user').order_by('-created_at')[:10]
    
    # Performance stats
    total_deliveries = Delivery.objects.filter(
        driver=driver,
        status='delivered'
    ).count()
    
    avg_rating = Delivery.objects.filter(
        driver=driver,
        rating__isnull=False
    ).aggregate(avg=Avg('rating'))['avg'] or 0
    
    # Completion rate
    accepted_count = Delivery.objects.filter(
        driver=driver,
        status__in=['accepted', 'picked_up', 'en_route', 'delivered']
    ).count()
    completed_count = Delivery.objects.filter(driver=driver, status='delivered').count()
    completion_rate = (completed_count / accepted_count * 100) if accepted_count > 0 else 0
    
    context = {
        'today_earnings': today_earnings,
        'today_count': today_count,
        'week_earnings': week_earnings,
        'month_earnings': month_earnings,
        'active_delivery': active_delivery,
        'available_deliveries': available_deliveries,
        'total_deliveries': total_deliveries,
        'avg_rating': avg_rating,
        'completion_rate': completion_rate,
        'is_available': driver.is_available_driver,
    }
    
    return render(request, 'driver/dashboard.html', context)


@login_required
@driver_required
def available_deliveries(request):
    """View all available deliveries"""
    # Show pending deliveries without a driver OR deliveries assigned to this driver that aren't accepted yet
    deliveries = Delivery.objects.filter(
        Q(status='pending', driver__isnull=True) |
        Q(status='assigned', driver=request.user)
    ).select_related('order__restaurant', 'order__user').order_by('-created_at')
    
    return render(request, 'driver/available.html', {'deliveries': deliveries})


@login_required
@driver_required
def accept_delivery(request, delivery_id):
    """Accept a delivery"""
    # Allow accepting both 'pending' and 'assigned' deliveries
    delivery = get_object_or_404(
        Delivery, 
        id=delivery_id,
        status__in=['pending', 'assigned']
    )
    
    # If it's assigned to another driver, reject
    if delivery.driver and delivery.driver != request.user:
        messages.error(request, 'This delivery is assigned to another driver.')
        return redirect('delivery:driver_dashboard')
    
    # Check if driver already has an active delivery (but allow accepting their assigned one)
    has_active = Delivery.objects.filter(
        driver=request.user,
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).exclude(id=delivery_id).exists()
    
    if has_active:
        messages.error(request, 'You already have an active delivery. Complete it first.')
        return redirect('delivery:driver_dashboard')
    
    if request.method == 'POST':
        # If it's pending, assign to driver first
        if delivery.status == 'pending':
            delivery.assign_to_driver(request.user)
        
        # Now accept the delivery (changes status from 'assigned' to 'accepted')
        delivery.accept_delivery()
        
        # Send notifications (Non-blocking)
        from core.utils.websocket_notifications import notify_customer_order_status
        notify_customer_order_status(
            delivery.order,
            'accepted',
            f'Driver {request.user.get_full_name()} has accepted your delivery'
        )
        
        messages.success(request, f'Delivery #{delivery.order.order_number} accepted!')
        return redirect('delivery:active_delivery', delivery_id=delivery.id)
    
    return redirect('delivery:driver_dashboard')


@login_required
@driver_required
def reject_delivery(request, delivery_id):
    """Reject a delivery"""
    delivery = get_object_or_404(Delivery, id=delivery_id, status='pending')
    
    if request.method == 'POST':
        messages.info(request, 'Delivery rejected.')
        return redirect('delivery:driver_dashboard')
    
    return redirect('delivery:driver_dashboard')


@login_required
@driver_required
def active_delivery(request, delivery_id):
    """View active delivery details"""
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    
    context = {
        'delivery': delivery,
        'order': delivery.order,
    }
    
    return render(request, 'driver/active_delivery.html', context)


@login_required
@driver_required
def mark_picked_up(request, delivery_id):
    """Mark order as picked up from restaurant"""
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    
    if request.method == 'POST':
        delivery.mark_picked_up()
        messages.success(request, 'Order marked as picked up!')
        return redirect('delivery:active_delivery', delivery_id=delivery.id)
    
    return redirect('delivery:active_delivery', delivery_id=delivery.id)


@login_required
@driver_required
def mark_delivered(request, delivery_id):
    """Mark order as delivered to customer"""
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    
    if request.method == 'POST':
        delivery.mark_delivered()
        messages.success(request, f'Delivery completed! You earned ${delivery.order.delivery_fee}')
        return redirect('delivery:driver_dashboard')
    
    return redirect('delivery:active_delivery', delivery_id=delivery.id)


@login_required
@driver_required
def delivery_history(request):
    """View delivery history with earnings"""
    deliveries = Delivery.objects.filter(
        driver=request.user,
        status='delivered'
    ).select_related('order__restaurant').order_by('-actual_delivery_time')
    
    # Date filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            deliveries = deliveries.filter(actual_delivery_time__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            deliveries = deliveries.filter(actual_delivery_time__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Calculate total earnings for filtered results
    total_earnings = deliveries.aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    # Pagination
    paginator = Paginator(deliveries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'deliveries': page_obj,
        'total_earnings': total_earnings,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'driver/history.html', context)


@login_required
@driver_required
def earnings_dashboard(request):
    """Detailed earnings dashboard"""
    driver = request.user
    today = timezone.now().date()
    
    # Time periods
    week_ago = today - timedelta(days=7)
    month_start = today.replace(day=1)
    
    # Earnings breakdown
    today_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__date=today
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    week_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=week_ago
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    month_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=month_start
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    # Lifetime earnings
    lifetime_earnings = Delivery.objects.filter(
        driver=driver,
        status='delivered'
    ).aggregate(total=Sum('order__delivery_fee'))['total'] or 0
    
    # Delivery counts
    today_count = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__date=today
    ).count()
    
    week_count = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=week_ago
    ).count()
    
    month_count = Delivery.objects.filter(
        driver=driver,
        status='delivered',
        actual_delivery_time__gte=month_start
    ).count()
    
    context = {
        'today_earnings': today_earnings,
        'today_count': today_count,
        'today_avg': (today_earnings / today_count) if today_count > 0 else 0,
        'week_earnings': week_earnings,
        'week_count': week_count,
        'week_avg': (week_earnings / week_count) if week_count > 0 else 0,
        'month_earnings': month_earnings,
        'month_count': month_count,
        'month_avg': (month_earnings / month_count) if month_count > 0 else 0,
        'lifetime_earnings': lifetime_earnings,
    }
    
    return render(request, 'driver/earnings.html', context)


@login_required
@driver_required
def toggle_availability(request):
    """Toggle driver online/offline status"""
    if request.method == 'POST':
        driver = request.user
        driver.is_available_driver = not driver.is_available_driver
        driver.save(update_fields=['is_available_driver'])
        
        status = 'online' if driver.is_available_driver else 'offline'
        messages.success(request, f'You are now {status}!')
    
    return redirect('delivery:driver_dashboard')
