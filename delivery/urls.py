from django.urls import path
from . import views
from . import driver_views as new_driver_views
from . import admin_views

app_name = 'delivery'

urlpatterns = [
    # Original tracking
    path('track/<int:delivery_id>/', views.delivery_tracking_view, name='delivery_tracking'),
    
    # Driver Dashboard - Enhanced
    path('driver/', new_driver_views.driver_dashboard, name='driver_dashboard'),
    path('driver/available/', new_driver_views.available_deliveries, name='available_deliveries'),
    path('driver/delivery/<int:delivery_id>/', new_driver_views.active_delivery, name='active_delivery'),
    path('driver/history/', new_driver_views.delivery_history, name='delivery_history'),
    path('driver/earnings/', new_driver_views.earnings_dashboard, name='earnings_dashboard'),
    path('driver/toggle-availability/', new_driver_views.toggle_availability, name='toggle_availability'),
    
    # Driver Delivery Actions
    path('driver/accept/<int:delivery_id>/', new_driver_views.accept_delivery, name='accept_delivery'),
    path('driver/reject/<int:delivery_id>/', new_driver_views.reject_delivery, name='reject_delivery'),
    path('driver/pickup/<int:delivery_id>/', new_driver_views.mark_picked_up, name='mark_picked_up'),
    path('driver/deliver/<int:delivery_id>/', new_driver_views.mark_delivered, name='mark_delivered'),
    
    # Original driver actions (keeping for backward compatibility)
    path('driver/update-status/<int:delivery_id>/', views.update_delivery_status, name='update_delivery_status'),
    path('driver/update-location/', views.update_driver_location, name='update_driver_location'),
    
    # Admin Driver Management
    path('admin/drivers/', admin_views.driver_applications_list, name='admin_driver_applications'),
    path('admin/drivers/<int:driver_id>/', admin_views.driver_application_detail, name='admin_driver_detail'),
    path('admin/drivers/<int:driver_id>/approve/', admin_views.approve_driver, name='admin_approve_driver'),
    path('admin/drivers/<int:driver_id>/reject/', admin_views.reject_driver, name='admin_reject_driver'),
    path('admin/drivers/<int:driver_id>/deactivate/', admin_views.deactivate_driver, name='admin_deactivate_driver'),
    
    # Admin Manual Assignment
    path('admin/manual-assignment/', admin_views.manual_assignment_view, name='admin_manual_assignment'),
    path('admin/assign/<int:delivery_id>/', admin_views.assign_driver_manually, name='admin_assign_driver'),
]
