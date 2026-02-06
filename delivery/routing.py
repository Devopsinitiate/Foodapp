"""
WebSocket URL routing for delivery app.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Driver notifications
    re_path(r'ws/driver/notifications/$', consumers.DriverNotificationConsumer.as_asgi()),
    
    # Vendor notifications
    re_path(r'ws/vendor/notifications/$', consumers.VendorNotificationConsumer.as_asgi()),
    
    # Customer order tracking
    re_path(r'ws/orders/(?P<order_id>\d+)/$', consumers.CustomerTrackingConsumer.as_asgi()),
]