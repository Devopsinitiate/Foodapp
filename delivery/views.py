"""Views for delivery tracking and driver management."""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Delivery, DeliveryLocation, DriverAvailability, DeliveryZone
from orders.models import Order


# ============ Template-based Views ============

@login_required
def delivery_tracking_view(request, delivery_id):
    """Delivery tracking page with map."""
    delivery = get_object_or_404(
        Delivery.objects.select_related('order', 'driver'),
        id=delivery_id
    )
    
    # Check if user has access
    if not (request.user == delivery.order.user or 
            request.user == delivery.driver or
            request.user == delivery.order.restaurant.owner or
            request.user.is_staff):
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    context = {
        'delivery': delivery,
        'order': delivery.order,
    }
    
    return render(request, 'delivery/tracking.html', context)


@login_required
def driver_dashboard_view(request):
    """Driver dashboard."""
    if not request.user.is_driver:
        messages.error(request, 'Access denied. Driver account required.')
        return redirect('home')
    
    # Get or create driver availability
    availability, created = DriverAvailability.objects.get_or_create(
        driver=request.user
    )
    
    # Get active deliveries
    active_deliveries = Delivery.objects.filter(
        driver=request.user,
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).select_related('order', 'order__restaurant')
    
    # Get available deliveries (pending assignment)
    available_deliveries = Delivery.objects.filter(
        status='pending',
        driver__isnull=True
    ).select_related('order', 'order__restaurant')[:10]
    
    # Get completed deliveries today
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    completed_today = Delivery.objects.filter(
        driver=request.user,
        status='delivered',
        actual_delivery_time__date=today
    ).count()
    
    context = {
        'availability': availability,
        'active_deliveries': active_deliveries,
        'available_deliveries': available_deliveries,
        'completed_today': completed_today,
    }
    
    return render(request, 'delivery/driver_dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_driver_availability(request):
    """Toggle driver online/offline status."""
    if not request.user.is_driver:
        return JsonResponse({'error': 'Not a driver'}, status=403)
    
    availability, created = DriverAvailability.objects.get_or_create(
        driver=request.user
    )
    
    if availability.is_online:
        availability.go_offline()
        status_text = 'offline'
    else:
        availability.go_online()
        status_text = 'online'
    
    return JsonResponse({
        'success': True,
        'status': status_text,
        'is_available': availability.is_available
    })


@login_required
@require_http_methods(["POST"])
def accept_delivery(request, delivery_id):
    """Driver accepts a delivery."""
    if not request.user.is_driver:
        return JsonResponse({'error': 'Not a driver'}, status=403)
    
    # Allow accepting deliveries in either 'pending' or 'assigned' status
    delivery = get_object_or_404(
        Delivery, 
        id=delivery_id, 
        status__in=['pending', 'assigned']
    )
    
    # Check if delivery is already assigned to another driver
    if delivery.driver and delivery.driver != request.user:
        return JsonResponse({
            'error': 'This delivery is already assigned to another driver'
        }, status=400)
    
    # Check if driver is available (only if delivery not already assigned to them)
    # If delivery is already assigned to this driver, they can accept it even if marked unavailable
    if not delivery.driver or delivery.driver != request.user:
        try:
            availability = DriverAvailability.objects.get(driver=request.user)
            # Check if driver is online (more important than is_available)
            if not availability.is_online:
                return JsonResponse({
                    'error': 'You must be online to accept deliveries'
                }, status=400)
            # Only check is_available for new assignments
            if not delivery.driver and not availability.is_available:
                return JsonResponse({
                    'error': 'You are currently busy with another delivery'
                }, status=400)
        except DriverAvailability.DoesNotExist:
            return JsonResponse({'error': 'Driver profile not found'}, status=400)
    
    # Assign delivery to driver if not already assigned
    if not delivery.driver:
        delivery.assign_to_driver(request.user)
        # Mark driver as unavailable (busy)
        try:
            availability = DriverAvailability.objects.get(driver=request.user)
            availability.is_available = False
            availability.save(update_fields=['is_available'])
        except DriverAvailability.DoesNotExist:
            pass
    
    # Accept the delivery
    delivery.accept_delivery()
    
    # Broadcast acceptance via WebSocket (Non-blocking)
    from core.utils.websocket_notifications import notify_customer_order_status
    notify_customer_order_status(
        delivery.order,
        'accepted',
        f'Driver {request.user.get_full_name()} accepted your delivery!',
        driver_name=request.user.get_full_name(),
        driver_phone=request.user.phone_number if hasattr(request.user, 'phone_number') else ''
    )
    
    return JsonResponse({
        'success': True,
        'message': 'Delivery accepted',
        'delivery_id': delivery.id
    })


@login_required
@require_http_methods(["POST"])
def reject_delivery(request, delivery_id):
    """Driver rejects a delivery assignment."""
    if not request.user.is_driver:
        return JsonResponse({'error': 'Not a driver'}, status=403)
    
    delivery = get_object_or_404(
        Delivery, 
        id=delivery_id, 
        driver=request.user,
        status__in=['assigned', 'pending']
    )
    
    # Get rejection reason
    reason = request.POST.get('reason', 'Driver rejected')
    
    # Mark as rejected
    from django.utils import timezone
    delivery.status = 'pending'
    delivery.driver = None
    delivery.rejected_at = timezone.now()
    delivery.rejection_reason = reason
    delivery.save()
    
    # Restore driver availability
    try:
        availability = DriverAvailability.objects.get(driver=request.user)
        if availability.is_online:
            availability.is_available = True
            availability.save(update_fields=['is_available'])
    except DriverAvailability.DoesNotExist:
        pass
    
    # Broadcast rejection via WebSocket (Non-blocking)
    from core.utils.websocket_notifications import notify_customer_order_status
    notify_customer_order_status(
        delivery.order,
        'rejected',
        'Driver rejected delivery. Finding another driver...'
    )
    
    # Trigger reassignment
    # Trigger reassignment (Safe)
    from delivery.tasks import assign_delivery_async
    from delivery.services import process_delivery_assignment
    from core.utils.task_helper import run_task_safe
    
    run_task_safe(assign_delivery_async, process_delivery_assignment, delivery.order.id)
    
    return JsonResponse({
        'success': True,
        'message': 'Delivery rejected. Reassigning to another driver.'
    })


@login_required
@require_http_methods(["POST"])
def update_delivery_status(request, delivery_id):
    """Update delivery status."""
    delivery = get_object_or_404(
        Delivery,
        id=delivery_id,
        driver=request.user
    )
    
    new_status = request.POST.get('status')
    
    # Broadcast update via WebSocket
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    
    if new_status == 'picked_up':
        delivery.mark_picked_up()
        # Sync order status
        delivery.order.status = 'out_for_delivery'
        delivery.order.save(update_fields=['status'])
        
    elif new_status == 'en_route':
        delivery.mark_en_route()
        # Sync order status
        delivery.order.status = 'out_for_delivery'
        delivery.order.save(update_fields=['status'])
        
    elif new_status == 'delivered':
        delivery.mark_delivered()
        # mark_delivered already updates order status to 'delivered' and sends notifications
    else:
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    return JsonResponse({
        'success': True,
        'status': delivery.status
    })



@login_required
@require_http_methods(["POST"])
def update_driver_location(request):
    """Update driver's current location."""
    if not request.user.is_driver:
        return JsonResponse({'error': 'Not a driver'}, status=403)
    
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')
    
    if not latitude or not longitude:
        return JsonResponse({'error': 'Missing coordinates'}, status=400)
    
    # Update driver availability location
    availability, created = DriverAvailability.objects.get_or_create(
        driver=request.user
    )
    availability.update_location(latitude, longitude)
    
    # Update active delivery location
    active_delivery = Delivery.objects.filter(
        driver=request.user,
        status__in=['accepted', 'picked_up', 'en_route']
    ).first()
    
    if active_delivery:
        active_delivery.update_location(latitude, longitude)
        
        # Create location history
        DeliveryLocation.objects.create(
            delivery=active_delivery,
            latitude=latitude,
            longitude=longitude
        )
    
    return JsonResponse({
        'success': True,
        'message': 'Location updated'
    })


# ============ REST API ViewSets ============

class DeliveryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for delivery management.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_driver:
            # Drivers see their deliveries
            return Delivery.objects.filter(driver=user)
        elif user.is_vendor:
            # Vendors see deliveries for their restaurants
            return Delivery.objects.filter(order__restaurant__owner=user)
        elif user.is_staff:
            # Admins see all
            return Delivery.objects.all()
        else:
            # Customers see their deliveries
            return Delivery.objects.filter(order__user=user)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Driver accepts delivery."""
        if not request.user.is_driver:
            return Response(
                {'error': 'Only drivers can accept deliveries'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        delivery = self.get_object()
        
        if delivery.status != 'pending':
            return Response(
                {'error': 'Delivery not available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        delivery.assign_to_driver(request.user)
        delivery.accept_delivery()
        
        return Response({'message': 'Delivery accepted'})
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update delivery status."""
        delivery = self.get_object()
        
        if delivery.driver != request.user:
            return Response(
                {'error': 'Not your delivery'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_status = request.data.get('status')
        
        if new_status == 'picked_up':
            delivery.mark_picked_up()
        elif new_status == 'en_route':
            delivery.mark_en_route()
        elif new_status == 'delivered':
            delivery.mark_delivered()
        else:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({'status': delivery.status})
    
    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        """Update driver location."""
        delivery = self.get_object()
        
        if delivery.driver != request.user:
            return Response(
                {'error': 'Not your delivery'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'Missing coordinates'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        delivery.update_location(latitude, longitude)
        
        # Create location history
        DeliveryLocation.objects.create(
            delivery=delivery,
            latitude=latitude,
            longitude=longitude
        )
        
        return Response({'message': 'Location updated'})


class DriverAvailabilityViewSet(viewsets.ModelViewSet):
    """
    API endpoint for driver availability.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_driver:
            return DriverAvailability.objects.filter(driver=self.request.user)
        return DriverAvailability.objects.none()
    
    @action(detail=False, methods=['post'])
    def go_online(self, request):
        """Set driver as online."""
        if not request.user.is_driver:
            return Response(
                {'error': 'Not a driver'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        availability, created = DriverAvailability.objects.get_or_create(
            driver=request.user
        )
        availability.go_online()
        
        return Response({'message': 'You are now online'})
    
    @action(detail=False, methods=['post'])
    def go_offline(self, request):
        """Set driver as offline."""
        if not request.user.is_driver:
            return Response(
                {'error': 'Not a driver'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        availability, created = DriverAvailability.objects.get_or_create(
            driver=request.user
        )
        availability.go_offline()
        
        return Response({'message': 'You are now offline'})
    
    @action(detail=False, methods=['post'])
    def update_location(self, request):
        """Update driver location."""
        if not request.user.is_driver:
            return Response(
                {'error': 'Not a driver'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'Missing coordinates'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        availability, created = DriverAvailability.objects.get_or_create(
            driver=request.user
        )
        availability.update_location(latitude, longitude)
        
        return Response({'message': 'Location updated'})