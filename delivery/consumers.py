"""
WebSocket consumers for real-time notifications.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class DriverNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for driver notifications.
    Handles real-time delivery assignments and status updates.
    """
    
    async def connect(self):
        """Accept WebSocket connection and add driver to notification group."""
        self.user = self.scope["user"]
        
        # Only allow authenticated drivers
        if self.user.is_anonymous or not self.user.is_driver:
            await self.close()
            return
        
        # Create driver-specific channel group
        self.driver_group_name = f"driver_{self.user.id}"
        
        # Join driver's personal notification group
        await self.channel_layer.group_add(
            self.driver_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to delivery notifications'
        }))
    
    async def disconnect(self, close_code):
        """Remove driver from notification group."""
        if hasattr(self, 'driver_group_name'):
            await self.channel_layer.group_discard(
                self.driver_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket (ping/pong, acknowledgments)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Heartbeat response
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            
            elif message_type == 'acknowledge':
                # Delivery notification acknowledged
                delivery_id = data.get('delivery_id')
                # Could log acknowledgment here
                pass
                
        except json.JSONDecodeError:
            pass
    
    async def new_delivery(self, event):
        """Send new delivery notification to driver."""
        await self.send(text_data=json.dumps({
            'type': 'new_delivery',
            'delivery_id': event['delivery_id'],
            'order_number': event['order_number'],
            'restaurant': event['restaurant'],
            'distance': event['distance'],
            'earnings': event['earnings'],
            'pickup_address': event.get('pickup_address', ''),
            'delivery_address': event.get('delivery_address', ''),
            'customer_name': event.get('customer_name', ''),
            'items': event.get('items', []),
            'total': event.get('total', 0),
        }))
    
    async def delivery_reassigned(self, event):
        """Notify driver that delivery was reassigned."""
        await self.send(text_data=json.dumps({
            'type': 'delivery_reassigned',
            'delivery_id': event['delivery_id'],
            'reason': event.get('reason', 'Reassigned to another driver')
        }))
    
    async def delivery_cancelled(self, event):
        """Notify driver that delivery was cancelled."""
        await self.send(text_data=json.dumps({
            'type': 'delivery_cancelled',
            'delivery_id': event['delivery_id'],
            'reason': event.get('reason', 'Order cancelled by customer')
        }))
    
    async def status_update(self, event):
        """Send delivery status update."""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'delivery_id': event['delivery_id'],
            'status': event['status'],
            'message': event.get('message', '')
        }))


class CustomerTrackingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for customer order tracking.
    Sends real-time driver location and ETA updates.
    """
    
    async def connect(self):
        """Join order-specific tracking group."""
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.order_group_name = f"order_{self.order_id}"
        
        # Join order tracking group
        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send current delivery status
        delivery_info = await self.get_delivery_info()
        if delivery_info:
            await self.send(text_data=json.dumps(delivery_info))
    
    async def disconnect(self, close_code):
        """Leave order tracking group."""
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle ping/pong for connection keep-alive."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except:
            pass
    
    async def location_update(self, event):
        """Send driver location update to customer."""
        await self.send(text_data=json.dumps({
            'type': 'location_update',
            'latitude': event['latitude'],
            'longitude': event['longitude'],
            'timestamp': event['timestamp'],
            'eta_minutes': event.get('eta_minutes')
        }))
    
    async def delivery_status(self, event):
        """Send delivery status update to customer."""
        await self.send(text_data=json.dumps({
            'type': 'delivery_status',
            'status': event['status'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))
    
    async def order_update(self, event):
        """
        Handle alias event for backward compatibility.
        Fixes ValueError: No handler for message type order_update
        """
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'status': event.get('status'),
            'message': event.get('message'),
            'timestamp': event.get('timestamp')
        }))
    
    @database_sync_to_async
    def get_delivery_info(self):
        """Get current delivery information."""
        from delivery.models import Delivery
        try:
            delivery = Delivery.objects.select_related(
                'driver', 'order'
            ).get(order_id=self.order_id)
            
            return {
                'type': 'initial_status',
                'status': delivery.status,
                'driver_name': delivery.driver.get_full_name() if delivery.driver else None,
                'driver_phone': delivery.driver.phone_number if delivery.driver else None,
                'current_latitude': float(delivery.current_latitude) if delivery.current_latitude else None,
                'current_longitude': float(delivery.current_longitude) if delivery.current_longitude else None,
            }
        except Delivery.DoesNotExist:
            return None


class VendorNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for vendor/restaurant owner notifications.
    Sends real-time notifications for new orders and updates.
    """
    
    async def connect(self):
        """Accept WebSocket connection and add vendor to notification group."""
        self.user = self.scope["user"]
        
        # Only allow authenticated vendors
        if self.user.is_anonymous or not self.user.is_vendor:
            await self.close()
            return
        
        # Get vendor's restaurant ID
        restaurant = await self.get_vendor_restaurant()
        if not restaurant:
            await self.close()
            return
        
        self.restaurant_id = restaurant['id']
        self.vendor_group_name = f"vendor_{self.user.id}"
        self.restaurant_group_name = f"restaurant_{self.restaurant_id}"
        
        # Join vendor's personal notification group
        await self.channel_layer.group_add(
            self.vendor_group_name,
            self.channel_name
        )
        
        # Join restaurant notification group
        await self.channel_layer.group_add(
            self.restaurant_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to vendor notifications',
            'restaurant_id': self.restaurant_id
        }))
    
    async def disconnect(self, close_code):
        """Remove vendor from notification groups."""
        if hasattr(self, 'vendor_group_name'):
            await self.channel_layer.group_discard(
                self.vendor_group_name,
                self.channel_name
            )
        if hasattr(self, 'restaurant_group_name'):
            await self.channel_layer.group_discard(
                self.restaurant_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle messages from WebSocket (ping/pong, acknowledgments)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Heartbeat response
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            
            elif message_type == 'acknowledge':
                # Order notification acknowledged
                order_id = data.get('order_id')
                # Could log acknowledgment here
                pass
                
        except json.JSONDecodeError:
            pass
    
    async def new_order(self, event):
        """Send new order notification to vendor."""
        await self.send(text_data=json.dumps({
            'type': 'new_order',
            'order_id': event['order_id'],
            'order_number': event['order_number'],
            'customer_name': event.get('customer_name', ''),
            'total': event.get('total', 0),
            'items_count': event.get('items_count', 0),
            'delivery_address': event.get('delivery_address', ''),
            'created_at': event.get('created_at', ''),
        }))
    
    async def order_status_update(self, event):
        """Send order status update to vendor."""
        await self.send(text_data=json.dumps({
            'type': 'order_status_update',
            'order_id': event['order_id'],
            'status': event['status'],
            'message': event.get('message', '')
        }))
    
    async def order_cancelled(self, event):
        """Notify vendor that order was cancelled."""
        await self.send(text_data=json.dumps({
            'type': 'order_cancelled',
            'order_id': event['order_id'],
            'reason': event.get('reason', 'Cancelled by customer')
        }))
    
    @database_sync_to_async
    def get_vendor_restaurant(self):
        """Get vendor's restaurant."""
        from restaurants.models import Restaurant
        try:
            restaurant = Restaurant.objects.get(owner=self.user)
            return {
                'id': restaurant.id,
                'name': restaurant.name
            }
        except Restaurant.DoesNotExist:
            return None