from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('orders', views.OrderViewSet, basename='order')
router.register('coupons', views.CouponViewSet, basename='coupon')

urlpatterns = [
    path('cart/', views.CartAPIView.as_view(), name='api_cart'),
    path('cart/add/', views.AddToCartAPIView.as_view(), name='api_cart_add'),
    path('cart/items/<int:pk>/', views.CartItemAPIView.as_view(), name='api_cart_item'),
    path('cart/clear/', views.ClearCartAPIView.as_view(), name='api_cart_clear'),
    path('coupons/validate/', views.ValidateCouponAPIView.as_view(), name='api_validate_coupon'),
    path('', include(router.urls)),
]