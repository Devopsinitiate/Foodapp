"""
Vendor dashboard views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import VendorProfile
from .forms import VendorApplicationForm, RestaurantForm, MenuItemForm
from .decorators import vendor_required
from restaurants.models import Restaurant, MenuItem, Category
from orders.models import Order, OrderItem


def vendor_application_view(request):
    """Vendor application form."""
    if request.user.is_authenticated and request.user.is_vendor:
        return redirect('vendors:dashboard')
    
    if request.method == 'POST':
        form = VendorApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            vendor_profile = form.save(commit=False)
            vendor_profile.user = request.user
            vendor_profile.save()
            
            # Update user type
            request.user.user_type = 'vendor'
            request.user.save()
            
            messages.success(
                request,
                'Your vendor application has been submitted successfully! '
                'We will review it and get back to you soon.'
            )
            return redirect('vendors:pending')
    else:
        form = VendorApplicationForm()
    
    return render(request, 'vendors/apply.html', {'form': form})


@login_required
def vendor_pending_view(request):
    """Pending approval page."""
    try:
        vendor_profile = request.user.vendor_profile
    except VendorProfile.DoesNotExist:
        return redirect('vendors:apply')
    
    return render(request, 'vendors/pending.html', {
        'vendor_profile': vendor_profile
    })


@vendor_required
def vendor_dashboard_view(request):
    """Main vendor dashboard."""
    vendor_restaurants = Restaurant.objects.filter(owner=request.user)
    
    # Get today's stats
    today = timezone.now().date()
    today_orders = Order.objects.filter(
        restaurant__owner=request.user,
        created_at__date=today
    )
    
    # Calculate stats
    stats = {
        'total_restaurants': vendor_restaurants.count(),
        'today_orders': today_orders.count(),
        'today_revenue': today_orders.filter(
            status='delivered'
        ).aggregate(Sum('total'))['total__sum'] or 0,
        'pending_orders': Order.objects.filter(
            restaurant__owner=request.user,
            status='pending'
        ).count(),
        'payment_pending_orders': Order.objects.filter(
            restaurant__owner=request.user,
            payment_status='pending'
        ).count(),
        'paid_orders': Order.objects.filter(
            restaurant__owner=request.user,
            payment_status='paid'
        ).count(),
        'cod_orders': Order.objects.filter(
            restaurant__owner=request.user,
            payment_status='cod'
        ).count(),
    }
    
    # Recent orders
    recent_orders = Order.objects.filter(
        restaurant__owner=request.user
    ).select_related('user', 'restaurant').order_by('-created_at')[:10]
    
    # Revenue chart data (last 7 days)
    chart_data = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        revenue = Order.objects.filter(
            restaurant__owner=request.user,
            created_at__date=date,
            status='delivered'
        ).aggregate(Sum('total'))['total__sum'] or 0
        chart_data.append({
            'date': date.strftime('%a'),
            'revenue': float(revenue)
        })
    
    context = {
        'stats': stats,
        'recent_orders': recent_orders,
        'chart_data': chart_data,
        'restaurants': vendor_restaurants,
    }
    
    return render(request, 'vendors/dashboard.html', context)


# Restaurant Management Views

@vendor_required
def restaurant_list_view(request):
    """List all restaurants owned by vendor."""
    restaurants = Restaurant.objects.filter(owner=request.user)
    return render(request, 'vendors/restaurants/list.html', {
        'restaurants': restaurants
    })


@vendor_required
def restaurant_create_view(request):
    """Create new restaurant."""
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            # Auto-verify restaurants for approved vendors
            restaurant.is_verified = True
            restaurant.save()
            form.save_m2m()  # Save many-to-many relationships
            messages.success(request, f'Restaurant "{restaurant.name}" created successfully!')
            return redirect('vendors:restaurant_list')
    else:
        form = RestaurantForm()
    
    return render(request, 'vendors/restaurants/form.html', {
        'form': form,
        'title': 'Add New Restaurant'
    })


@vendor_required
def restaurant_edit_view(request, pk):
    """Edit existing restaurant."""
    restaurant = get_object_or_404(Restaurant, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        form = RestaurantForm(request.POST, request.FILES, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, f'Restaurant "{restaurant.name}" updated successfully!')
            return redirect('vendors:restaurant_list')
    else:
        form = RestaurantForm(instance=restaurant)
    
    return render(request, 'vendors/restaurants/form.html', {
        'form': form,
        'restaurant': restaurant,
        'title': f'Edit {restaurant.name}'
    })


@vendor_required
def restaurant_delete_view(request, pk):
    """Delete restaurant."""
    restaurant = get_object_or_404(Restaurant, pk=pk, owner=request.user)
    
    if request.method == 'POST':
        name = restaurant.name
        restaurant.delete()
        messages.success(request, f'Restaurant "{name}" deleted successfully!')
        return redirect('vendors:restaurant_list')
    
    return render(request, 'vendors/restaurants/delete_confirm.html', {
        'restaurant': restaurant
    })


# Menu Management Views

@vendor_required
def menu_list_view(request):
    """List all menu items for vendor's restaurants."""
    restaurant_id = request.GET.get('restaurant')
    category_id = request.GET.get('category')
    search = request.GET.get('search', '')
    
    menu_items = MenuItem.objects.filter(
        restaurant__owner=request.user
    ).select_related('restaurant', 'category')
    
    if restaurant_id:
        menu_items = menu_items.filter(restaurant_id=restaurant_id)
    
    if category_id:
        menu_items = menu_items.filter(category_id=category_id)
    
    if search:
        menu_items = menu_items.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    restaurants = Restaurant.objects.filter(owner=request.user)
    categories = Category.objects.all()
    
    return render(request, 'vendors/menu/list.html', {
        'menu_items': menu_items,
        'restaurants': restaurants,
        'categories': categories,
        'selected_restaurant': restaurant_id,
        'selected_category': category_id,
        'search': search,
    })


@vendor_required
def menu_item_create_view(request):
    """Create new menu item."""
    if request.method == 'POST':
        form = MenuItemForm(request.POST, request.FILES)
        if form.is_valid():
            menu_item = form.save(commit=False)
            # Ensure restaurant belongs to vendor
            if menu_item.restaurant.owner != request.user:
                messages.error(request, 'Invalid restaurant selection.')
                return redirect('vendors:menu_list')
            menu_item.save()
            messages.success(request, f'Menu item "{menu_item.name}" created successfully!')
            return redirect('vendors:menu_list')
    else:
        form = MenuItemForm()
        # Filter restaurants to only show vendor's restaurants
        form.fields['restaurant'].queryset = Restaurant.objects.filter(owner=request.user)
    
    return render(request, 'vendors/menu/form.html', {
        'form': form,
        'title': 'Add New Menu Item'
    })


@vendor_required
def menu_item_edit_view(request, pk):
    """Edit existing menu item."""
    menu_item = get_object_or_404(
        MenuItem,
        pk=pk,
        restaurant__owner=request.user
    )
    
    if request.method == 'POST':
        form = MenuItemForm(request.POST, request.FILES, instance=menu_item)
        if form.is_valid():
            form.save()
            messages.success(request, f'Menu item "{menu_item.name}" updated successfully!')
            return redirect('vendors:menu_list')
    else:
        form = MenuItemForm(instance=menu_item)
        form.fields['restaurant'].queryset = Restaurant.objects.filter(owner=request.user)
    
    return render(request, 'vendors/menu/form.html', {
        'form': form,
        'menu_item': menu_item,
        'title': f'Edit {menu_item.name}'
    })


@vendor_required
def menu_item_delete_view(request, pk):
    """Delete menu item."""
    menu_item = get_object_or_404(
        MenuItem,
        pk=pk,
        restaurant__owner=request.user
    )
    
    if request.method == 'POST':
        name = menu_item.name
        menu_item.delete()
        messages.success(request, f'Menu item "{name}" deleted successfully!')
        return redirect('vendors:menu_list')
    
    return render(request, 'vendors/menu/delete_confirm.html', {
        'menu_item': menu_item
    })


# Order Management Views

@vendor_required
def order_dashboard_view(request):
    """Vendor order dashboard."""
    orders = Order.objects.filter(
        restaurant__owner=request.user
    ).select_related('user', 'restaurant')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Order by newest first
    orders = orders.order_by('-created_at')
    
    # Stats by status
    status_counts = {
        'pending': orders.filter(status='pending').count(),
        'confirmed': orders.filter(status='confirmed').count(),
        'preparing': orders.filter(status='preparing').count(),
        'ready': orders.filter(status='ready').count(),
        'out_for_delivery': orders.filter(status='out_for_delivery').count(),
    }
    
    # Payment status stats
    payment_status_counts = {
        'paid': orders.filter(payment_status='paid').count(),
        'cod': orders.filter(payment_status='cod').count(),
        'pending': orders.filter(payment_status='pending').count(),
        'failed': orders.filter(payment_status='failed').count(),
    }
    
    # Add payment status counts to context
    status_counts.update(payment_status_counts)
    
    return render(request, 'vendors/orders/dashboard.html', {
        'orders': orders,
        'status_counts': status_counts,
        'current_status': status_filter,
    })


@vendor_required
def order_detail_view(request, order_number):
    """Vendor order detail view."""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        restaurant__owner=request.user
    )
    
    return render(request, 'vendors/orders/detail.html', {
        'order': order
    })


@vendor_required
def order_update_status_view(request, order_number):
    """Update order status and trigger delivery workflow."""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        restaurant__owner=request.user
    )
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            old_status = order.status
            order.status = new_status
            
            # Set confirmed_at timestamp when status changes to confirmed
            if new_status == 'confirmed' and old_status == 'pending':
                order.confirmed_at = timezone.now()
            
            order.save()
            
            # Send email notification to customer about status change (Non-blocking)
            from users.emails import send_order_status_email, send_email_async
            send_email_async(send_order_status_email, order)
            
            # Import required modules for delivery workflow
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from delivery.models import Delivery
            
            channel_layer = get_channel_layer()
            
            # WORKFLOW STAGE 1: Order Confirmed - Assign to Driver
            if new_status == 'confirmed' and old_status == 'pending':
                try:
                    # Check if delivery record exists, create if not
                    delivery, created = Delivery.objects.get_or_create(
                        order=order,
                        defaults={
                            'status': 'pending',
                            'pickup_latitude': order.restaurant.latitude if hasattr(order.restaurant, 'latitude') else None,
                            'pickup_longitude': order.restaurant.longitude if hasattr(order.restaurant, 'longitude') else None,
                        }
                    )
                    
                    # Trigger async delivery assignment via Celery (with safe fallback)
                    from delivery.tasks import assign_delivery_async
                    from delivery.services import process_delivery_assignment
                    from core.utils.task_helper import run_task_safe
                    
                    run_task_safe(assign_delivery_async, process_delivery_assignment, order.id)
                    

                    messages.success(request, f'Order confirmed! Finding available driver...')
                except Exception as e:
                    print(f"Delivery assignment error: {e}")
                    messages.success(request, f'Order status updated to {order.get_status_display()}')
            
            # WORKFLOW STAGE 2: Order Ready - Notify Assigned Driver
            elif new_status == 'ready' and old_status in ['confirmed', 'preparing']:
                try:
                    delivery = Delivery.objects.select_related('driver').get(order=order)
                    if delivery.driver:
                        from core.utils.websocket_notifications import notify_driver_delivery_update
                        notify_driver_delivery_update(
                            delivery.driver, 
                            delivery, 
                            'ready_for_pickup', 
                            f'🍽️ Order #{order.order_number} is ready for pickup at {order.restaurant.name}!'
                        )
                        messages.success(request, f'Order marked as ready! Driver {delivery.driver.get_full_name()} notified.')
                    else:
                        messages.warning(request, f'Order marked as ready but no driver assigned yet.')
                except Delivery.DoesNotExist:
                    messages.warning(request, f'Order status updated, but no delivery record found. Please assign a driver manually.')
                except Exception as e:
                    messages.success(request, f'Order status updated to {order.get_status_display()}')
            
            # WORKFLOW STAGE 3: Out for Delivery - Update delivery status
            elif new_status == 'out_for_delivery':
                try:
                    delivery = Delivery.objects.get(order=order)
                    if delivery.status != 'en_route':
                        delivery.mark_en_route()
                except Delivery.DoesNotExist:
                    pass
                messages.success(request, f'Order status updated to {order.get_status_display()}')
            
            # Default for other status changes
            else:
                messages.success(request, f'Order status updated to {order.get_status_display()}')
            
            # Broadcast status update via WebSocket to customer tracking page (Non-blocking)
            from core.utils.websocket_notifications import notify_customer_order_status
            notify_customer_order_status(
                order, 
                new_status, 
                f'Order status updated to {order.get_status_display()}'
            )
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('vendors:order_detail', order_number=order_number)


# Analytics Views

@vendor_required
def analytics_dashboard_view(request):
    """Analytics dashboard."""
    # Date range
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)
    
    orders = Order.objects.filter(
        restaurant__owner=request.user,
        created_at__gte=start_date
    )
    
    # Revenue stats
    total_revenue = orders.filter(
        status='delivered'
    ).aggregate(Sum('total'))['total__sum'] or 0
    
    total_orders = orders.count()
    avg_order_value = orders.aggregate(Avg('total'))['total__avg'] or 0
    
    # Popular items
    popular_items = OrderItem.objects.filter(
        order__restaurant__owner=request.user,
        order__created_at__gte=start_date
    ).values(
        'menu_item__name'
    ).annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('total_price')
    ).order_by('-total_quantity')[:10]
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'popular_items': popular_items,
        'days': days,
    }
    
    return render(request, 'vendors/analytics/dashboard.html', context)
