from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('restaurants', views.RestaurantViewSet, basename='restaurant')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('menu-items', views.MenuItemViewSet, basename='menuitem')
router.register('reviews', views.ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]