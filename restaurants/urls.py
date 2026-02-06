from django.urls import path
from . import views
from . import favorite_views
from . import review_views
from . import coupon_views

app_name = 'restaurants'

urlpatterns = [
    path('', views.restaurant_list_view, name='list'),
    path('favorites/', favorite_views.favorites_list_view, name='favorites'),
    path('<int:restaurant_id>/toggle-favorite/', favorite_views.toggle_favorite_view, name='toggle_favorite'),
    
    # Review URLs
    path('review/submit/<str:order_number>/', review_views.submit_review_view, name='submit_review'),
    
    path('<slug:slug>/', views.restaurant_detail_view, name='detail'),
    path('<slug:restaurant_slug>/menu/', views.menu_view, name='menu'),
    
    # Vendor URLs
    path('vendor/dashboard/', views.vendor_dashboard_view, name='vendor_dashboard'),
    path('vendor/orders/', views.vendor_orders_view, name='vendor_orders'),
    path('vendor/orders/<int:order_id>/confirm/', views.vendor_confirm_order, name='vendor_confirm_order'),
    path('vendor/orders/<int:order_id>/mark-ready/', views.vendor_mark_ready, name='vendor_mark_ready'),
    
    # Vendor Coupon Management
    path('vendor/coupons/', coupon_views.vendor_coupons_list, name='vendor_coupons'),
    path('vendor/coupons/create/', coupon_views.create_coupon, name='create_coupon'),
    path('vendor/coupons/<int:pk>/edit/', coupon_views.edit_coupon, name='edit_coupon'),
    path('vendor/coupons/<int:pk>/toggle/', coupon_views.toggle_coupon, name='toggle_coupon'),
    path('vendor/coupons/<int:pk>/analytics/', coupon_views.coupon_analytics, name='coupon_analytics'),
]