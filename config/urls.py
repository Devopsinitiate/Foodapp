"""
Main URL Configuration for Food Ordering Application
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from users import views as user_views

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Homepage
    path('', user_views.home_view, name='home'),
    path('polish-demo/', user_views.polish_demo_view, name='polish_demo'),
    
    # App URLs
    path('', include('users.urls')),
    path('restaurants/', include('restaurants.urls')),
    path('orders/', include('orders.urls')),
    path('delivery/', include('delivery.urls')),
    path('payments/', include('payments.urls')),
    path('vendors/', include('vendors.urls')),
    path('platform-admin/', include('platform_admin.urls')),
    
    # API URLs
    path('api/users/', include('users.api_urls')),
    path('api/restaurants/', include('restaurants.api_urls')),
    path('api/orders/', include('orders.api_urls')),
    path('api/delivery/', include('delivery.api_urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom admin site headers
admin.site.site_header = 'EmpressDish Admin'
admin.site.site_title = 'EmpressDish Admin Portal'
admin.site.index_title = 'Welcome to EmpressDish Administration'