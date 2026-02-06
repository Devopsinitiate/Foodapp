"""
URL configuration for vendors app.
"""
from django.urls import path
from . import views
from restaurants import review_views

app_name = 'vendors'

urlpatterns = [
    # Application
    path('apply/', views.vendor_application_view, name='apply'),
    path('pending/', views.vendor_pending_view, name='pending'),
    
    # Dashboard
    path('dashboard/', views.vendor_dashboard_view, name='dashboard'),
    
    # Restaurant Management
    path('restaurants/', views.restaurant_list_view, name='restaurant_list'),
    path('restaurants/add/', views.restaurant_create_view, name='restaurant_create'),
    path('restaurants/<int:pk>/edit/', views.restaurant_edit_view, name='restaurant_edit'),
    path('restaurants/<int:pk>/delete/', views.restaurant_delete_view, name='restaurant_delete'),
    
    # Menu Management
    path('menu/', views.menu_list_view, name='menu_list'),
    path('menu/add/', views.menu_item_create_view, name='menu_item_create'),
    path('menu/<int:pk>/edit/', views.menu_item_edit_view, name='menu_item_edit'),
    path('menu/<int:pk>/delete/', views.menu_item_delete_view, name='menu_item_delete'),
    
    # Order Management
    path('orders/', views.order_dashboard_view, name='order_dashboard'),
    path('orders/<str:order_number>/', views.order_detail_view, name='order_detail'),
    path('orders/<str:order_number>/update-status/', views.order_update_status_view, name='order_update_status'),
    
    # Analytics
    path('analytics/', views.analytics_dashboard_view, name='analytics_dashboard'),
    
    # Review Management
    path('reviews/', review_views.vendor_manage_reviews, name='manage_reviews'),
    path('reviews/<int:review_id>/respond/', review_views.vendor_respond_to_review, name='respond_to_review'),
]
