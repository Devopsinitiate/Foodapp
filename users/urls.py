from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    path('orders/', views.order_history_view, name='order_history'),
    path('addresses/', views.saved_addresses_view, name='saved_addresses'),
    path('favorites/', views.favorites_view, name='favorites'),
    path('favorites/add/<int:restaurant_id>/', views.add_favorite, name='add_favorite'),
    path('favorites/remove/<int:restaurant_id>/', views.remove_favorite, name='remove_favorite'),
]