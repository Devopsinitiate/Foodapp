"""
Platform Admin Views - Platform Management Dashboard
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.http import JsonResponse
from django.core.paginator import Paginator

from users.models import User
from restaurants.models import Restaurant
from orders.models import Order
from delivery.models import Delivery


@staff_member_required
def dashboard_overview(request):
    """
    Main admin dashboard with analytics and stats.
    """
    # Date ranges
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    
    # Revenue stats
    total_revenue = Order.objects.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    revenue_last_30_days = Order.objects.filter(
        payment_status='paid',
        created_at__gte=last_30_days
    ).aggregate(total=Sum('total'))['total'] or 0
    
    # Order stats
    total_orders = Order.objects.count()
    orders_last_30_days = Order.objects.filter(
        created_at__gte=last_30_days
    ).count()
    
    # Calculate percentage changes
    orders_previous_30 = Order.objects.filter(
        created_at__gte=last_30_days - timedelta(days=30),
        created_at__lt=last_30_days
    ).count()
    orders_change = ((orders_last_30_days - orders_previous_30) / orders_previous_30 * 100) if orders_previous_30 > 0 else 0
    
    # Platform stats
    stats = {
        'total_revenue': total_revenue,
        'revenue_last_30_days': revenue_last_30_days,
        'total_orders': total_orders,
        'orders_last_30_days': orders_last_30_days,
        'orders_change': orders_change,
        
        'active_restaurants': Restaurant.objects.filter(is_active=True).count(),
        'pending_restaurants': Restaurant.objects.filter(is_verified=False, is_active=True).count(),
        
        'active_drivers': User.objects.filter(user_type='driver', is_active=True).count(),
        'pending_drivers': User.objects.filter(user_type='driver', is_verified_driver=False, is_active=True).count(),
        
        'total_customers': User.objects.filter(user_type='customer', is_active=True).count(),
        
        'avg_rating': Restaurant.objects.filter(is_active=True).aggregate(
            avg=Avg('average_rating')
        )['avg'] or 0,
    }
    
    # Orders by status
    orders_by_status = list(Order.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status'))
    
    # Recent orders
    recent_orders = Order.objects.select_related(
        'user', 'restaurant'
    ).order_by('-created_at')[:10]
    
    # Recent registrations
    recent_users = User.objects.filter(
        date_joined__gte=last_7_days
    ).order_by('-date_joined')[:5]
    
    # Top restaurants by orders
    top_restaurants = Restaurant.objects.filter(
        is_active=True
    ).annotate(
        order_count=Count('orders')
    ).order_by('-order_count')[:5]
    
    context = {
        'stats': stats,
        'orders_by_status': orders_by_status,
        'recent_orders': recent_orders,
        'recent_users': recent_users,
        'top_restaurants': top_restaurants,
    }
    
    return render(request, 'platform_admin/dashboard.html', context)


@staff_member_required
def manage_restaurants(request):
    """
    Restaurant management - list all restaurants with filters.
    """
    # Filters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    restaurants = Restaurant.objects.select_related('owner').annotate(
        order_count=Count('orders'),
        total_revenue=Sum('orders__total', filter=Q(orders__payment_status='paid'))
    )
    
    # Apply filters
    if status_filter == 'pending':
        restaurants = restaurants.filter(is_verified=False)
    elif status_filter == 'active':
        restaurants = restaurants.filter(is_verified=True, is_active=True)
    elif status_filter == 'inactive':
        restaurants = restaurants.filter(is_active=False)
    
    if search_query:
        restaurants = restaurants.filter(
            Q(name__icontains=search_query) |
            Q(owner__username__icontains=search_query) |
            Q(owner__email__icontains=search_query)
        )
    
    restaurants = restaurants.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(restaurants, 20)
    page_number = request.GET.get('page')
    restaurants_page = paginator.get_page(page_number)
    
    context = {
        'restaurants': restaurants_page,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'platform_admin/restaurants.html', context)


@staff_member_required
def approve_restaurant(request, restaurant_id):
    """
    Approve a pending restaurant.
    """
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    
    if request.method == 'POST':
        restaurant.is_verified = True
        restaurant.save()
        
        # Send notification email
        try:
            from utils.emails import send_html_email
            send_html_email(
                subject=f"🎉 {restaurant.name} Approved!",
                template_name="emails/restaurant_approved.html",
                context={'restaurant': restaurant},
                recipient_list=[restaurant.owner.email]
            )
        except Exception as e:
            print(f"Failed to send approval email: {e}")
        
        messages.success(request, f'{restaurant.name} has been approved!')
        return redirect('platform_admin:restaurants')
    
    return render(request, 'platform_admin/approve_restaurant.html', {
        'restaurant': restaurant
    })


@staff_member_required
def reject_restaurant(request, restaurant_id):
    """
    Reject a pending restaurant with reason.
    """
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Not specified')
        restaurant.is_active = False
        restaurant.save()
        
        # Send notification email
        try:
            from utils.emails import send_html_email
            send_html_email(
                subject=f"Restaurant Application - {restaurant.name}",
                template_name="emails/restaurant_rejected.html",
                context={'restaurant': restaurant, 'reason': reason},
                recipient_list=[restaurant.owner.email]
            )
        except Exception as e:
            print(f"Failed to send rejection email: {e}")
        
        messages.success(request, f'{restaurant.name} has been rejected.')
        return redirect('platform_admin:restaurants')
    
    return render(request, 'platform_admin/reject_restaurant.html', {
        'restaurant': restaurant
    })


@staff_member_required
def manage_drivers(request):
    """
    Driver management and verification.
    """
    status_filter = request.GET.get('status', 'all')
    
    drivers = User.objects.filter(user_type='driver').annotate(
        delivery_count=Count('deliveries', filter=Q(deliveries__status='delivered'))
    )
    
    if status_filter == 'pending':
        drivers = drivers.filter(is_verified_driver=False)
    elif status_filter == 'active':
        drivers = drivers.filter(is_verified_driver=True, is_active=True)
    elif status_filter == 'inactive':
        drivers = drivers.filter(is_active=False)
    
    drivers = drivers.order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(drivers, 20)
    page_number = request.GET.get('page')
    drivers_page = paginator.get_page(page_number)
    
    context = {
        'drivers': drivers_page,
        'status_filter': status_filter,
    }
    
    return render(request, 'platform_admin/drivers.html', context)


@staff_member_required
def verify_driver(request, driver_id):
    """
    Verify and approve a driver.
    """
    driver = get_object_or_404(User, id=driver_id, user_type='driver')
    
    if request.method == 'POST':
        driver.is_verified_driver = True
        driver.save()
        
        messages.success(request, f'{driver.get_full_name()} has been verified as a driver!')
        return redirect('platform_admin:drivers')
    
    return render(request, 'platform_admin/verify_driver.html', {
        'driver': driver
    })


@staff_member_required
def monitor_orders(request):
    """
    Monitor all platform orders.
    """
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    orders = Order.objects.select_related(
        'user', 'restaurant'
    ).prefetch_related('items')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(restaurant__name__icontains=search_query)
        )
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    orders_page = paginator.get_page(page_number)
    
    context = {
        'orders': orders_page,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'platform_admin/orders.html', context)
