"""
Views for restaurant browsing and management.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Count
from django.core.paginator import Paginator

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny

from .models import Restaurant, MenuItem, Category, Review
from .serializers import (
    RestaurantListSerializer, RestaurantDetailSerializer,
    RestaurantCreateUpdateSerializer, MenuItemListSerializer,
    MenuItemDetailSerializer, MenuItemCreateUpdateSerializer,
    CategorySerializer, ReviewSerializer, ReviewCreateSerializer,
    RestaurantStatsSerializer
)


# ============ Template-based Views ============

def restaurant_list_view(request):
    """List all restaurants with filtering."""
    restaurants = Restaurant.objects.filter(
        is_active=True
    ).select_related('owner').prefetch_related('categories')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        restaurants = restaurants.filter(
            Q(name__icontains=search_query) |
            Q(cuisine_type__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Filter by category
    category_slug = request.GET.get('category')
    if category_slug:
        restaurants = restaurants.filter(categories__slug=category_slug)
    
    # Filter by accepting orders
    if request.GET.get('open_now'):
        restaurants = restaurants.filter(is_accepting_orders=True)
    
    # Sort
    sort_by = request.GET.get('sort', 'rating')
    if sort_by == 'rating':
        restaurants = restaurants.order_by('-average_rating', 'name')
    elif sort_by == 'delivery_time':
        restaurants = restaurants.order_by('estimated_delivery_time')
    elif sort_by == 'delivery_fee':
        restaurants = restaurants.order_by('delivery_fee')
    elif sort_by == 'name':
        restaurants = restaurants.order_by('name')
    
    # Pagination
    paginator = Paginator(restaurants, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get all categories for filter
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'restaurants': page_obj,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_slug,
        'sort_by': sort_by,
    }
    
    return render(request, 'restaurants/list.html', context)


def restaurant_detail_view(request, slug):
    """Restaurant detail page with menu."""
    restaurant = get_object_or_404(
        Restaurant.objects.select_related('owner')
        .prefetch_related('categories', 'menu_items', 'reviews'),
        slug=slug,
        is_active=True
    )
    
    # Get menu items grouped by category
    menu_items = restaurant.menu_items.filter(
        is_available=True
    ).select_related('category').order_by('category__order', 'name')
    
    # Filter by category if specified
    category_id = request.GET.get('category')
    if category_id:
        menu_items = menu_items.filter(category_id=category_id)
    
    # Get recent reviews
    reviews = restaurant.reviews.select_related('user').order_by('-created_at')[:10]
    
    # Calculate rating distribution
    all_reviews = restaurant.reviews.all()
    total_reviews = all_reviews.count()
    rating_dist = {i: {'count': 0, 'percent': 0} for i in range(1, 6)}
    
    if total_reviews > 0:
        from django.db.models import Count
        counts = all_reviews.values('rating').annotate(total=Count('id'))
        for c in counts:
            rating = c['rating']
            count = c['total']
            rating_dist[rating] = {
                'count': count,
                'percent': int((count / total_reviews) * 100)
            }
    
    # Check if user has ordered from this restaurant (to allow review)
    latest_order = None
    if request.user.is_authenticated:
        # Get the latest delivered order that hasn't been reviewed yet
        latest_order = restaurant.orders.filter(
            user=request.user,
            status='delivered'
        ).exclude(
            reviews__user=request.user
        ).order_by('-created_at').first()
    
    context = {
        'restaurant': restaurant,
        'menu_items': menu_items,
        'reviews': reviews,
        'latest_order': latest_order,
        'rating_dist': rating_dist,
        'menu_categories': Category.objects.filter(
            menu_items__restaurant=restaurant,
            is_active=True
        ).distinct()
    }
    
    return render(request, 'restaurants/detail.html', context)


def menu_view(request, restaurant_slug):
    """Standalone menu view."""
    restaurant = get_object_or_404(
        Restaurant,
        slug=restaurant_slug,
        is_active=True
    )
    
    menu_items = restaurant.menu_items.filter(
        is_available=True
    ).select_related('category').order_by('category__order', 'name')
    
    context = {
        'restaurant': restaurant,
        'menu_items': menu_items,
    }
    
    return render(request, 'restaurants/menu.html', context)


@login_required
def vendor_dashboard_view(request):
    """Vendor dashboard for managing restaurants."""
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('home')
    
    restaurants = Restaurant.objects.filter(owner=request.user)
    
    # Get statistics
    total_orders = sum(r.total_orders for r in restaurants)
    total_revenue = 0  # Calculate from orders
    
    context = {
        'restaurants': restaurants,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
    }
    
    return render(request, 'restaurants/vendor_dashboard.html', context)


@login_required
def vendor_orders_view(request):
    """Vendor order management page with filtering."""
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('home')
    
    from orders.models import Order
    from django.db.models import Sum, Q
    from django.utils import timezone
    from datetime import timedelta
    
    # Get vendor's restaurants
    vendor_restaurants = Restaurant.objects.filter(owner=request.user)
    
    if not vendor_restaurants.exists():
        messages.warning(request, 'You need to create a restaurant first.')
        return redirect('restaurants:vendor_dashboard')
    
    # Get all orders for vendor's restaurants
    orders = Order.objects.filter(
        restaurant__in=vendor_restaurants
    ).select_related('restaurant', 'user').prefetch_related('items__menu_item').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    # Filter by payment status
    payment_filter = request.GET.get('payment_status')
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)
    
    # Filter by payment method
    payment_method_filter = request.GET.get('payment_method')
    if payment_method_filter:
        orders = orders.filter(payment_method=payment_method_filter)
    
    # Search by order number or customer name
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    
    # Calculate today's statistics
    today = timezone.now().date()
    today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
    
    today_orders = Order.objects.filter(
        restaurant__in=vendor_restaurants,
        created_at__gte=today_start
    )
    
    today_stats = {
        'total_orders': today_orders.count(),
        'pending_orders': today_orders.filter(status='pending').count(),
        'confirmed_orders': today_orders.filter(status__in=['confirmed', 'preparing', 'ready']).count(),
        'completed_orders': today_orders.filter(status='delivered').count(),
        'total_revenue': today_orders.filter(payment_status__in=['paid', 'cod']).aggregate(Sum('total'))['total__sum'] or 0,
        'paid_orders': today_orders.filter(payment_status='paid').count(),
        'cod_orders': today_orders.filter(payment_status='cod').count(),
    }
    
    # Get counts for filter tabs
    status_counts = {
        'all': Order.objects.filter(restaurant__in=vendor_restaurants).count(),
        'pending': orders.filter(status='pending').count() if status_filter == 'all' else Order.objects.filter(restaurant__in=vendor_restaurants, status='pending').count(),
        'confirmed': orders.filter(status='confirmed').count() if status_filter == 'all' else Order.objects.filter(restaurant__in=vendor_restaurants, status='confirmed').count(),
        'preparing': orders.filter(status='preparing').count() if status_filter == 'all' else Order.objects.filter(restaurant__in=vendor_restaurants, status='preparing').count(),
        'ready': orders.filter(status='ready').count() if status_filter == 'all' else Order.objects.filter(restaurant__in=vendor_restaurants, status='ready').count(),
        'delivered': orders.filter(status='delivered').count() if status_filter == 'all' else Order.objects.filter(restaurant__in=vendor_restaurants, status='delivered').count(),
    }
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'today_stats': today_stats,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
        'payment_method_filter': payment_method_filter,
        'search_query': search_query,
        'status_counts': status_counts,
        'vendor_restaurants': vendor_restaurants,
    }
    
    return render(request, 'restaurants/vendor_orders.html', context)


@login_required
def vendor_confirm_order(request, order_id):
    """Vendor confirms pending order."""
    if not request.user.is_vendor:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from orders.models import Order
    from django.http import JsonResponse
    from django.views.decorators.http import require_http_methods
    
    try:
        order = Order.objects.select_related('restaurant').get(
            id=order_id,
            restaurant__owner=request.user
        )
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    
    if order.status != 'pending':
        return JsonResponse({'error': 'Only pending orders can be confirmed'}, status=400)
    
    # Confirm the order
    order.mark_as_confirmed()
    
    # Send order confirmed email to customer (Non-blocking)
    from utils.emails import send_order_confirmed_email, send_email_async
    send_email_async(send_order_confirmed_email, order)
    
    # Send WebSocket notification to customer (Non-blocking)
    from core.utils.websocket_notifications import notify_customer_order_status
    notify_customer_order_status(
        order,
        'confirmed',
        'Your order has been confirmed and is being prepared!'
    )
    
    # Trigger delivery assignment - call synchronously with fallback
    try:
        from delivery.assignment import assign_delivery_to_driver
        from core.utils.websocket_notifications import notify_driver_new_delivery, notify_customer_order_status
        
        # Assign driver synchronously
        delivery = assign_delivery_to_driver(order.id)
        
        if delivery and delivery.driver:
            # Send WebSocket notifications (Non-blocking)
            notify_driver_new_delivery(delivery.driver, delivery)
            notify_customer_order_status(
                order,
                'driver_assigned',
                f'Driver {delivery.driver.get_full_name()} is on the way to pick up your order!'
            )
            
            # Try to send email via Celery, fallback to non-blocking sync
            try:
                from delivery.tasks import notify_driver_new_delivery as notify_task
                notify_task.delay(delivery.driver.id, delivery.id)
            except Exception:
                # Celery not available, send emails non-blockingly
                from utils.emails import send_driver_new_delivery_email, send_driver_assigned_email, send_email_async
                send_email_async(send_driver_new_delivery_email, delivery)
                send_email_async(send_driver_assigned_email, order, delivery)
        
    except Exception as e:
        print(f"Delivery assignment error: {e}")
    
    return JsonResponse({
        'success': True,
        'message': 'Order confirmed successfully',
        'order_number': order.order_number,
        'new_status': order.status
    })



@login_required
def vendor_mark_ready(request, order_id):
    """Vendor marks order as ready for pickup."""
    if not request.user.is_vendor:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from orders.models import Order
    from django.http import JsonResponse
    
    try:
        order = Order.objects.select_related('restaurant').get(
            id=order_id,
            restaurant__owner=request.user
        )
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    
    if order.status not in ['confirmed', 'preparing']:
        return JsonResponse({'error': 'Order must be confirmed or preparing'}, status=400)
    
    # Mark as ready
    order.status = 'ready'
    order.save(update_fields=['status'])
    
    # Notify driver via WebSocket if delivery exists (Non-blocking)
    if hasattr(order, 'delivery') and order.delivery:
        from core.utils.websocket_notifications import notify_driver_order_ready
        notify_driver_order_ready(order.delivery.driver_id, order)
    
    return JsonResponse({
        'success': True,
        'message': 'Order marked as ready',
        'order_number': order.order_number,
        'new_status': order.status
    })



# ============ REST API ViewSets ============

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for browsing categories.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]


class RestaurantViewSet(viewsets.ModelViewSet):
    """
    API endpoint for restaurant management.
    List, retrieve, create, update restaurants.
    """
    queryset = Restaurant.objects.filter(is_active=True)
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'cuisine_type', 'description']
    ordering_fields = ['average_rating', 'delivery_fee', 'estimated_delivery_time']
    ordering = ['-average_rating']
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RestaurantListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return RestaurantCreateUpdateSerializer
        return RestaurantDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(categories__slug=category)
        
        # Filter by accepting orders
        if self.request.query_params.get('open_now') == 'true':
            queryset = queryset.filter(is_accepting_orders=True)
        
        # Filter by cuisine type
        cuisine = self.request.query_params.get('cuisine')
        if cuisine:
            queryset = queryset.filter(cuisine_type__icontains=cuisine)
        
        return queryset.distinct()
    
    def perform_create(self, serializer):
        """Ensure user is vendor when creating restaurant."""
        user = self.request.user
        if not user.is_vendor:
            raise PermissionError("Only vendors can create restaurants.")
        serializer.save(owner=user)
    
    @action(detail=True, methods=['get'])
    def menu(self, request, slug=None):
        """Get restaurant menu items."""
        restaurant = self.get_object()
        menu_items = restaurant.menu_items.filter(is_available=True)
        
        # Filter by category
        category = request.query_params.get('category')
        if category:
            menu_items = menu_items.filter(category__slug=category)
        
        serializer = MenuItemListSerializer(menu_items, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, slug=None):
        """Get restaurant reviews."""
        restaurant = self.get_object()
        reviews = restaurant.reviews.order_by('-created_at')
        
        # Pagination
        page = self.paginate_queryset(reviews)
        if page is not None:
            serializer = ReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_review(self, request, slug=None):
        """Add review for restaurant."""
        restaurant = self.get_object()
        
        # Check if user has ordered from this restaurant
        has_ordered = restaurant.orders.filter(
            user=request.user,
            status='delivered'
        ).exists()
        
        if not has_ordered:
            return Response(
                {'error': 'You must order from this restaurant before reviewing.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already reviewed
        if restaurant.reviews.filter(user=request.user).exists():
            return Response(
                {'error': 'You have already reviewed this restaurant.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ReviewCreateSerializer(
            data=request.data,
            context={'request': request, 'restaurant': restaurant}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def stats(self, request, slug=None):
        """Get restaurant statistics (vendor only)."""
        restaurant = self.get_object()
        
        # Check if user owns this restaurant
        if request.user != restaurant.owner:
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculate statistics
        from django.db.models import Sum, Avg
        from orders.models import Order
        
        orders = Order.objects.filter(restaurant=restaurant, payment_status='paid')
        
        stats = {
            'total_orders': orders.count(),
            'total_revenue': orders.aggregate(Sum('total'))['total__sum'] or 0,
            'average_order_value': orders.aggregate(Avg('total'))['total__avg'] or 0,
            'total_menu_items': restaurant.menu_items.count(),
            'active_menu_items': restaurant.menu_items.filter(is_available=True).count(),
            'average_rating': restaurant.average_rating,
            'total_reviews': restaurant.total_reviews,
        }
        
        serializer = RestaurantStatsSerializer(stats)
        serializer = RestaurantStatsSerializer(stats)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def toggle_favorite(self, request, slug=None):
        """Toggle restaurant favorite status."""
        restaurant = self.get_object()
        user = request.user
        
        if user.favorite_restaurants.filter(pk=restaurant.pk).exists():
            user.favorite_restaurants.remove(restaurant)
            is_favorite = False
            message = 'Removed from favorites'
        else:
            user.favorite_restaurants.add(restaurant)
            is_favorite = True
            message = 'Added to favorites'
            
        return Response({
            'is_favorite': is_favorite,
            'message': message
        })



class MenuItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for menu item management.
    """
    queryset = MenuItem.objects.filter(is_available=True)
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'name', 'total_orders']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MenuItemListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return MenuItemCreateUpdateSerializer
        return MenuItemDetailSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by restaurant
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        # Filter by dietary preferences
        if self.request.query_params.get('vegetarian') == 'true':
            queryset = queryset.filter(is_vegetarian=True)
        if self.request.query_params.get('vegan') == 'true':
            queryset = queryset.filter(is_vegan=True)
        if self.request.query_params.get('gluten_free') == 'true':
            queryset = queryset.filter(is_gluten_free=True)
        
        # Filter by featured
        if self.request.query_params.get('featured') == 'true':
            queryset = queryset.filter(is_featured=True)
        
        return queryset
    
    def perform_create(self, serializer):
        """Ensure user owns the restaurant when creating menu item."""
        restaurant = serializer.validated_data['restaurant']
        if self.request.user != restaurant.owner:
            raise PermissionError("You don't own this restaurant.")
        serializer.save()
    
    def perform_update(self, serializer):
        """Ensure user owns the restaurant when updating menu item."""
        menu_item = self.get_object()
        if self.request.user != menu_item.restaurant.owner:
            raise PermissionError("You don't own this restaurant.")
        serializer.save()


class ReviewViewSet(viewsets.ModelViewSet):
    """
    API endpoint for review management.
    """
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by restaurant
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        
        # Filter by user
        if self.request.query_params.get('my_reviews') == 'true':
            queryset = queryset.filter(user=self.request.user)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReviewCreateSerializer
        return ReviewSerializer
    
    def perform_create(self, serializer):
        """Create review with current user."""
        serializer.save(user=self.request.user)
    
    def perform_update(self, serializer):
        """Ensure user can only update their own reviews."""
        review = self.get_object()
        if self.request.user != review.user:
            raise PermissionError("You can only edit your own reviews.")
        serializer.save()
    
    def perform_destroy(self, instance):
        """Ensure user can only delete their own reviews."""
        if self.request.user != instance.user:
            raise PermissionError("You can only delete your own reviews.")
        instance.delete()