from django.urls import path
from . import views
from . import coupon_views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_view, name='cart'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('list/', views.order_list_view, name='list'),
    path('order/<str:order_number>/', views.order_detail_view, name='detail'),
    path('order/<str:order_number>/track/', views.order_tracking_view, name='tracking'),
    path('order/<str:order_number>/cancel/', views.cancel_order_view, name='cancel'),
    
    # Coupon endpoints
    path('coupon/apply/', coupon_views.apply_coupon_view, name='apply_coupon'),
    path('coupon/remove/', coupon_views.remove_coupon_view, name='remove_coupon'),
]