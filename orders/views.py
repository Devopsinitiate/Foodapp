"""
Views for order and cart management.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import Order, OrderItem, Cart, CartItem, Coupon
from .serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderCreateSerializer,
    OrderUpdateSerializer, CartSerializer, CartItemSerializer,
    CartItemCreateSerializer, CouponSerializer, CouponValidateSerializer
)
from restaurants.models import MenuItem


# ============ Template-based Views ============

@login_required
def order_list_view(request):
    """Order history page."""
    orders = Order.objects.filter(user=request.user).select_related('restaurant').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
    }
    
    return render(request, 'orders/list.html', context)


@login_required
def cart_view(request):
    """Shopping cart page."""
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.cart_items.select_related('menu_item__restaurant').all()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
    }
    
    return render(request, 'orders/cart.html', context)


@login_required
def checkout_view(request):
    """Checkout page."""
    from django.conf import settings
    
    cart = get_object_or_404(Cart, user=request.user)
    
    if not cart.cart_items.exists():
        messages.warning(request, 'Your cart is empty.')
        return redirect('orders:cart')
    
    # Check if all items are from the same restaurant
    restaurants = set(item.menu_item.restaurant for item in cart.cart_items.all())
    if len(restaurants) > 1:
        messages.error(request, 'All items must be from the same restaurant.')
        return redirect('orders:cart')
    
    restaurant = restaurants.pop()
    
    if request.method == 'POST':
        # Handle checkout form submission
        # This will be processed via API in the JavaScript
        pass
    
    context = {
        'cart': cart,
        'restaurant': restaurant,
        'user': request.user,
        'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
    }
    
    return render(request, 'orders/checkout.html', context)


@login_required
def order_detail_view(request, order_number):
    """Order detail page."""
    order = get_object_or_404(
        Order.objects.select_related('restaurant', 'user')
        .prefetch_related('items__menu_item'),
        order_number=order_number,
        user=request.user
    )
    
    context = {
        'order': order,
    }
    
    return render(request, 'orders/order_detail.html', context)


@login_required
def order_tracking_view(request, order_number):
    """Order tracking page with real-time updates."""
    order = get_object_or_404(
        Order.objects.select_related('restaurant'),
        order_number=order_number,
        user=request.user
    )
    
    # Get delivery info if exists
    delivery = getattr(order, 'delivery', None)
    
    context = {
        'order': order,
        'delivery': delivery,
    }
    
    return render(request, 'orders/tracking.html', context)


@login_required
def cancel_order_view(request, order_number):
    """Cancel order (within 5 minutes of placement)."""
    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )
    
    # Check if order can be cancelled
    if not order.can_be_cancelled:
        messages.error(request, 'This order cannot be cancelled. It has already been processed.')
        return redirect('orders:order_detail', order_number=order_number)
    
    # Check 5-minute time limit
    if not order.can_be_cancelled_by_customer():
        messages.error(request, 'Cancellation period has expired. Orders can only be cancelled within 5 minutes of placement.')
        return redirect('orders:order_detail', order_number=order_number)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Customer request')
        
        # Update order status
        order.status = 'cancelled'
        order.cancellation_reason = reason
        order.save()
        
        # Send cancellation emails
        # Send cancellation emails
        try:
            from utils.emails import send_order_cancellation_email
            send_order_cancellation_email(order)
        except Exception as e:
            print(f"Failed to send cancellation email: {e}")
        
        # TODO: Initiate refund if payment was made
        if order.payment_status == 'paid':
            # Refund logic will be implemented later
            messages.info(request, 'Your refund will be processed within 3-5 business days.')
        
        messages.success(request, f'Order #{order.order_number} has been cancelled successfully.')
        return redirect('orders:list')
    
    context = {
        'order': order,
    }
    
    return render(request, 'orders/cancel_confirm.html', context)


# ============ REST API ViewSets ============

class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for order management.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        elif self.action == 'create':
            return OrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        return OrderDetailSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.select_related('restaurant', 'user').prefetch_related('items')
        
        # Filter based on user role
        if user.is_vendor:
            # Vendors see orders for their restaurants
            queryset = queryset.filter(restaurant__owner=user)
        elif user.is_driver:
            # Drivers see their assigned deliveries
            queryset = queryset.filter(delivery__driver=user)
        elif user.is_staff:
            # Admins see all orders
            pass
        else:
            # Customers see only their orders
            queryset = queryset.filter(user=user)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by payment status
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        return queryset.order_by('-created_at')
    
    def create(self, request, *args, **kwargs):
        """Create new order."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        
        # Handle payment method - set on order model
        payment_method = request.data.get('payment_method', 'online')
        order.payment_method = payment_method
        
        if payment_method == 'cod':
            # For Cash on Delivery, set payment_status to 'cod'
            order.payment_status = 'cod'
            order.save(update_fields=['payment_method', 'payment_status'])
            print(f"📦 COD Order created: {order.order_number} - payment_method='cod', payment_status='cod'")
        else:
            # For online payment, keep payment_status as 'pending'
            order.save(update_fields=['payment_method'])
            print(f"💳 Online payment order created: {order.order_number} - payment_method='online', payment_status='pending'")
        
        # Send confirmation email
        try:
            from utils.emails import send_order_confirmation, send_vendor_new_order
            send_order_confirmation(order)
            # Notify vendor of new order
            send_vendor_new_order(order)
        except Exception as e:
            # Don't fail order creation if email fails
            print(f"Failed to send confirmation email: {e}")
        
        # Send WebSocket notification to vendor
        try:
            from core.utils.websocket_notifications import notify_vendor_new_order
            notify_vendor_new_order(order)
        except Exception as e:
            print(f"Failed to send WebSocket notification: {e}")
        
        # Clear user's cart after order creation
        try:
            cart = Cart.objects.get(user=request.user)
            cart.clear()
        except Cart.DoesNotExist:
            pass
        
        # Return order details
        response_serializer = OrderDetailSerializer(order)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order."""
        order = self.get_object()
        
        if not order.can_be_cancelled:
            return Response(
                {'error': 'Order cannot be cancelled at this stage.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.cancellation_reason = request.data.get('reason', '')
        order.save()
        
        # Send cancellation emails
        try:
            from utils.emails import send_order_cancellation_email
            send_order_cancellation_email(order)
        except Exception as e:
            print(f"Failed to send cancellation email: {e}")
        
        return Response({'message': 'Order cancelled successfully.'})
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm order (vendor only)."""
        order = self.get_object()
        
        # Check if user is the restaurant owner
        if request.user != order.restaurant.owner:
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status != 'pending':
            return Response(
                {'error': 'Only pending orders can be confirmed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.mark_as_confirmed()
        
        # Only create delivery record if it's a delivery order
        if order.delivery_type == 'delivery':
            from delivery.models import Delivery
            from delivery.tasks import assign_delivery_async
            from delivery.services import process_delivery_assignment
            from core.utils.task_helper import run_task_safe
            
            delivery, created = Delivery.objects.get_or_create(
                order=order,
                defaults={
                    'status': 'pending',
                    'driver': None,
                    'pickup_latitude': order.restaurant.latitude,
                    'pickup_longitude': order.restaurant.longitude,
                    'delivery_latitude': order.delivery_latitude,
                    'delivery_longitude': order.delivery_longitude,
                    'estimated_delivery_time': order.estimated_delivery_time
                }
            )
            
            # Trigger async delivery assignment (with safe fallback)
            run_task_safe(assign_delivery_async, process_delivery_assignment, order.id)
        else:
            # For pickup orders, we might want to set status to 'ready' directly or keep it as 'confirmed'
            # Until vendor marks it as 'Ready for Pickup'
            logger.info(f"Order {order.order_number} is a PICKUP order. Skipping delivery assignment.")
        
        # Broadcast status update to customer
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"order_{order.id}",
                    {
                        'type': 'delivery_status',
                        'status': 'confirmed',
                        'message': 'Order confirmed! Finding available driver...',
                        'timestamp': timezone.now().isoformat()
                    }
                )
        except Exception as e:
            print(f"WebSocket broadcast error: {e}")
            
        return Response({'message': 'Order confirmed successfully. Finding driver...'})
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get order statistics for current user."""
        user = request.user
        
        if user.is_vendor:
            # Vendor statistics
            orders = Order.objects.filter(restaurant__owner=user, payment_status='paid')
        else:
            # Customer statistics
            orders = Order.objects.filter(user=user, payment_status='paid')
        
        stats = {
            'total_orders': orders.count(),
            'total_spent': orders.aggregate(Sum('total'))['total__sum'] or 0,
            'pending_orders': orders.filter(status__in=['pending', 'confirmed', 'preparing']).count(),
            'completed_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
        }
        
        return Response(stats)


# ============ Cart API Views ============

class CartAPIView(APIView):
    """
    Get current user's cart.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class AddToCartAPIView(APIView):
    """
    Add item to cart.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        menu_item_id = serializer.validated_data['menu_item_id']
        quantity = serializer.validated_data['quantity']
        customizations = serializer.validated_data.get('customizations', {})
        
        # Get or create cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        # Get menu item
        menu_item = MenuItem.objects.get(id=menu_item_id)
        
        # Check if item already in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item,
            defaults={
                'quantity': quantity,
                'customizations': customizations
            }
        )
        
        if not created:
            # Update quantity if item already exists
            cart_item.quantity += quantity
            cart_item.save()
        
        # Return updated cart
        cart_serializer = CartSerializer(cart)
        return Response(cart_serializer.data, status=status.HTTP_201_CREATED)


class CartItemAPIView(APIView):
    """
    Update or delete cart item.
    """
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, pk):
        """Update cart item quantity."""
        cart_item = get_object_or_404(
            CartItem,
            pk=pk,
            cart__user=request.user
        )
        
        quantity = request.data.get('quantity')
        if quantity:
            cart_item.quantity = int(quantity)
            cart_item.save()
        
        serializer = CartItemSerializer(cart_item)
        return Response(serializer.data)
    
    def delete(self, request, pk):
        """Remove item from cart."""
        cart_item = get_object_or_404(
            CartItem,
            pk=pk,
            cart__user=request.user
        )
        
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClearCartAPIView(APIView):
    """
    Clear all items from cart.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
            cart.clear()
            return Response({'message': 'Cart cleared successfully.'})
        except Cart.DoesNotExist:
            return Response(
                {'error': 'Cart not found.'},
                status=status.HTTP_404_NOT_FOUND
            )


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for browsing coupons.
    """
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        now = timezone.now()
        
        # Only show valid coupons
        queryset = queryset.filter(
            valid_from__lte=now,
            valid_until__gte=now
        )
        
        return queryset


class ValidateCouponAPIView(APIView):
    """
    Validate coupon code and calculate discount.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        coupon = serializer.context['coupon']
        order_total = serializer.validated_data['order_total']
        
        discount_amount = coupon.calculate_discount(order_total)
        
        return Response({
            'valid': True,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': coupon.discount_value,
            'discount_amount': discount_amount,
            'final_total': order_total - discount_amount
        })