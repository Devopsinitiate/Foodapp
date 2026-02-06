"""
Platform Admin URLs
"""
from django.urls import path
from . import views

app_name = 'platform_admin'

urlpatterns = [
    # Dashboard overview
    path('', views.dashboard_overview, name='dashboard'),
    
    # Restaurant management
    path('restaurants/', views.manage_restaurants, name='restaurants'),
    path('restaurants/<int:restaurant_id>/approve/', views.approve_restaurant, name='approve_restaurant'),
    path('restaurants/<int:restaurant_id>/reject/', views.reject_restaurant, name='reject_restaurant'),
    
    # Driver management
    path('drivers/', views.manage_drivers, name='drivers'),
    path('drivers/<int:driver_id>/verify/', views.verify_driver, name='verify_driver'),
    
    # Order monitoring
    path('orders/', views.monitor_orders, name='orders'),
]
