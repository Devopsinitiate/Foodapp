"""
Views for favorite restaurants functionality.
"""
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .models import Restaurant


@login_required
@require_http_methods(['POST'])
def toggle_favorite_view(request, restaurant_id):
    """Toggle restaurant favorite status (AJAX)."""
    restaurant = get_object_or_404(Restaurant, id=restaurant_id, is_active=True)
    
    if restaurant in request.user.favorite_restaurants.all():
        request.user.favorite_restaurants.remove(restaurant)
        is_favorite = False
        message = f'{restaurant.name} removed from favorites'
    else:
        request.user.favorite_restaurants.add(restaurant)
        is_favorite = True
        message = f'{restaurant.name} added to favorites'
    
    return JsonResponse({
        'success': True,
        'is_favorite': is_favorite,
        'message': message,
        'favorites_count': request.user.favorite_restaurants.count()
    })


@login_required
def favorites_list_view(request):
    """Display user's favorite restaurants."""
    favorites = request.user.favorite_restaurants.filter(
        is_active=True
    ).select_related('owner').prefetch_related('categories')
    
    context = {
        'restaurants': favorites,
        'is_favorites_page': True,
    }
    
    return render(request, 'restaurants/favorites.html', context)
