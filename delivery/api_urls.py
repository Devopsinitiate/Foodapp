"""
API URL routes for delivery management.
"""
from django.urls import path
from . import api_views

app_name = 'delivery_api'

urlpatterns = [
    # Driver order management
    path('available-orders/', api_views.available_orders, name='available_orders'),
    path('accept/<int:delivery_id>/', api_views.accept_delivery, name='accept_delivery'),
    path('reject/<int:delivery_id>/', api_views.reject_delivery, name='reject_delivery'),
    path('active/', api_views.active_delivery, name='active_delivery'),
    path('active-deliveries/', api_views.driver_active_deliveries, name='driver_active_deliveries'),
    
    # Delivery status updates
    path('update-status/<int:delivery_id>/', api_views.update_delivery_status, name='update_status'),
    path('update-location/', api_views.update_location, name='update_location'),
]