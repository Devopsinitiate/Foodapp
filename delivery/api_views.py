"""
API views for driver delivery management.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from delivery.models import Delivery, DriverAvailability, DeliveryLocation
from delivery.assignment import reassign_delivery


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_orders(request):
    """Get list of available orders for driver to accept."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can access this endpoint'}, status=403)
    
    # Get deliveries assigned to this driver that haven't been accepted yet
    assigned_deliveries = Delivery.objects.filter(
        driver=request.user,
        status='assigned'
    ).select_related('order', 'order__restaurant', 'order__user')
    
    pending_deliveries = []
    for delivery in assigned_deliveries:
        pending_deliveries.append({
            'delivery_id': delivery.id,
            'order_number': delivery.order.order_number,
            'restaurant_name': delivery.order.restaurant.name,
            'restaurant_address': delivery.order.restaurant.address,
            'customer_name': delivery.order.user.get_full_name(),
            'delivery_address': delivery.order.delivery_address,
            'distance_km': float(delivery.distance_km) if delivery.distance_km else 0,
            'estimated_earnings': float(delivery.order.total * 0.15),  # 15% commission
            'assigned_at': delivery.assigned_at.isoformat() if delivery.assigned_at else None,
        })
    
    return Response({'deliveries': pending_deliveries})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_delivery(request, delivery_id):
    """Driver accepts an assigned delivery."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can accept deliveries'}, status=403)
    
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    
    if delivery.status != 'assigned':
        return Response({'error': 'Delivery is not in assigned status'}, status=400)
    
    # Accept delivery
    delivery.accept_delivery()
    
    # Update order status
    delivery.order.status = 'confirmed'
    delivery.order.save()
    
    return Response({
        'message': 'Delivery accepted successfully',
        'delivery_id': delivery.id,
        'status': delivery.status
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_delivery(request, delivery_id):
    """Driver rejects an assigned delivery."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can reject deliveries'}, status=403)
    
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    
    if delivery.status != 'assigned':
        return Response({'error': 'Delivery is not in assigned status'}, status=400)
    
    reason = request.data.get('reason', 'No reason provided')
    
    # Mark driver as available again
    try:
        availability = DriverAvailability.objects.get(driver=request.user)
        availability.is_available = True
        availability.save()
    except DriverAvailability.DoesNotExist:
        pass
    
    # Try to reassign to another driver
    new_delivery = reassign_delivery(delivery.id)
    
    if new_delivery and new_delivery.driver:
        message = f'Delivery reassigned to another driver'
    else:
        message = 'Delivery marked as pending - no available drivers'
    
    return Response({
        'message': message,
        'reason': reason
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_delivery_status(request, delivery_id):
    """Update delivery status (picked_up, en_route, delivered)."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can update delivery status'}, status=403)
    
    delivery = get_object_or_404(Delivery, id=delivery_id, driver=request.user)
    new_status = request.data.get('status')
    
    if new_status not in ['picked_up', 'en_route', 'delivered']:
        return Response({'error': 'Invalid status'}, status=400)
    
    # Import WebSocket utilities
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    channel_layer = get_channel_layer()
    
    # Update status
    if new_status == 'picked_up':
        delivery.mark_picked_up()
        delivery.order.status = 'out_for_delivery'
        delivery.order.save(update_fields=['status'])
        
    elif new_status == 'en_route':
        delivery.mark_en_route()
        delivery.order.status = 'out_for_delivery'
        delivery.order.save(update_fields=['status'])
        
    elif new_status == 'delivered':
        delivery.mark_delivered()
        # mark_delivered already updates order status and sends notifications
        
        # Make driver available again
        try:
            availability = DriverAvailability.objects.get(driver=request.user)
            availability.is_available = True
            availability.increment_deliveries(successful=True)
            availability.save()
        except DriverAvailability.DoesNotExist:
            pass
    
    return Response({
        'message': f'Delivery status updated to {new_status}',
        'delivery_id': delivery.id,
        'status': delivery.status
    })



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_location(request):
    """Update driver's current location."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can update location'}, status=403)
    
    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')
    
    if not latitude or not longitude:
        return Response({'error': 'Latitude and longitude are required'}, status=400)
    
    # Update driver availability location
    try:
        availability = DriverAvailability.objects.get(driver=request.user)
        availability.update_location(latitude, longitude)
    except DriverAvailability.DoesNotExist:
        return Response({'error': 'Driver availability not found'}, status=404)
    
    # Update active delivery location if exists
    active_delivery = Delivery.objects.filter(
        driver=request.user,
        status__in=['accepted', 'picked_up', 'en_route']
    ).first()
    
    if active_delivery:
        active_delivery.update_location(latitude, longitude)
        
        # Save location history
        DeliveryLocation.objects.create(
            delivery=active_delivery,
            latitude=latitude,
            longitude=longitude
        )
    
    return Response({
        'message': 'Location updated successfully',
        'latitude': latitude,
        'longitude': longitude
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_delivery(request):
    """Get driver's current active delivery."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can access this endpoint'}, status=403)
    
    delivery = Delivery.objects.filter(
        driver=request.user,
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).select_related('order', 'order__restaurant', 'order__user').first()
    
    if not delivery:
        return Response({'active_delivery': None})
    
    return Response({
        'active_delivery': {
            'delivery_id': delivery.id,
            'order_number': delivery.order.order_number,
            'status': delivery.status,
            'restaurant': {
                'name': delivery.order.restaurant.name,
                'address': delivery.order.restaurant.address,
                'latitude': float(delivery.pickup_latitude) if delivery.pickup_latitude else None,
                'longitude': float(delivery.pickup_longitude) if delivery.pickup_longitude else None,
            },
            'customer': {
                'name': delivery.order.user.get_full_name(),
                'phone': delivery.order.contact_phone,
                'address': delivery.order.delivery_address,
                'latitude': float(delivery.delivery_latitude) if delivery.delivery_latitude else None,
                'longitude': float(delivery.delivery_longitude) if delivery.delivery_longitude else None,
            },
            'items': [
                {
                    'name': item.item_name,
                    'quantity': item.quantity,
                    'price': float(item.total_price)
                }
                for item in delivery.order.items.all()
            ],
            'total': float(delivery.order.total),
            'earnings': float(delivery.order.total * 0.15),
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def driver_active_deliveries(request):
    """Get all active deliveries for the driver dashboard."""
    if not request.user.is_driver:
        return Response({'error': 'Only drivers can access this endpoint'}, status=403)
    
    deliveries = Delivery.objects.filter(
        driver=request.user,
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).select_related('order', 'order__restaurant', 'order__user').order_by('-created_at')
    
    delivery_list = []
    for delivery in deliveries:
        delivery_list.append({
            'id': delivery.id,
            'order_number': delivery.order.order_number,
            'restaurant': delivery.order.restaurant.name,
            'status': delivery.status,
            'status_display': delivery.get_status_display(),
            'customer_name': delivery.order.user.get_full_name(),
            'customer_phone': delivery.order.contact_phone,
            'delivery_address': delivery.order.delivery_address,
        })
    
    return Response({'active_deliveries': delivery_list})
