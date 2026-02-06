"""
Complete views for user authentication and profile management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q, Sum, Count, Avg
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from .models import User, UserProfile
from .serializers import (
    UserSerializer, UserRegistrationSerializer, UserUpdateSerializer,
    PasswordChangeSerializer, UserProfileSerializer
)


# ============ Template-based Views ============

def home_view(request):
    """Homepage view."""
    from restaurants.models import Restaurant, Category, MenuItem
    from orders.models import Order
    from django.db.models import Count, Avg, Q
    
    # Get featured restaurants
    featured_restaurants = Restaurant.objects.filter(
        is_active=True,
        is_verified=True
    ).order_by('-average_rating')[:12]
    
    # Get all categories with restaurant count
    categories = Category.objects.filter(is_active=True).annotate(
        restaurant_count=Count('restaurants', filter=Q(restaurants__is_active=True))
    ).order_by('order')[:8]
    
    # Get popular dishes (most ordered)
    popular_dishes = MenuItem.objects.filter(
        is_available=True,
        restaurant__is_active=True
    ).select_related('restaurant').annotate(
        order_count=Count('order_items')
    ).order_by('-order_count')[:8]
    
    # Platform stats
    stats = {
        'restaurant_count': Restaurant.objects.filter(is_active=True).count(),
        'total_orders': Order.objects.filter(status='delivered').count(),
        'avg_rating': Restaurant.objects.filter(is_active=True).aggregate(avg=Avg('average_rating'))['avg'] or 4.5,
    }
    
    context = {
        'featured_restaurants': featured_restaurants,
        'restaurants': featured_restaurants,  # For template compatibility
        'categories': categories,
        'popular_dishes': popular_dishes,
        'stats': stats,
    }
    
    return render(request, 'home.html', context)


def register_view(request):
    """User registration page."""
    if request.user.is_authenticated:
        return redirect('home')
    
    # Clear any existing messages when first loading the register page (GET request)
    if request.method == 'GET':
        storage = messages.get_messages(request)
        storage.used = True
    
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        user_type = request.POST.get('user_type', 'customer')
        
        # Validation
        if not all([username, email, password, password2]):
            messages.error(request, 'All required fields must be filled.')
            return render(request, 'users/register.html')
        
        if password != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/register.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'users/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'users/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'users/register.html')
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                user_type=user_type
            )
            
            # Create profile
            UserProfile.objects.create(user=user)
            
            # Send welcome email
            try:
                from utils.emails import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                # Don't fail registration if email fails
                print(f"Failed to send welcome email: {e}")
            
            messages.success(request, 'Registration successful! Please login.')
            return redirect('users:login')
            
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'users/register.html')
    
    return render(request, 'users/register.html')


def login_view(request):
    """User login page."""
    if request.user.is_authenticated:
        return redirect('home')
    
    # Clear any existing messages when first loading the login page (GET request)
    if request.method == 'GET':
        # Get the storage and clear it
        storage = messages.get_messages(request)
        storage.used = True
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')
        
        if not username or not password:
            messages.error(request, 'Please provide both username and password.')
            return render(request, 'users/login.html')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                
                # Set session expiry
                if not remember_me:
                    request.session.set_expiry(0)  # Session expires on browser close
                
                # Get next URL or redirect to home
                next_url = request.GET.get('next', 'home')
                
                # Redirect based on user type
                if user.is_vendor and user.is_active_vendor:
                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect('vendors:dashboard')
                elif user.is_driver:
                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect('home')  # Update when driver dashboard is created
                else:
                    messages.success(request, f'Welcome back, {user.username}!')
                    return redirect(next_url)
            else:
                messages.error(request, 'Your account is disabled.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'users/login.html')


def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('home')


@login_required
def profile_view(request):
    """User profile page."""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Handle profile update
        user = request.user
        
        # Update user fields
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.phone_number = request.POST.get('phone_number', '').strip()
        user.street_address = request.POST.get('street_address', '').strip()
        user.city = request.POST.get('city', '').strip()
        user.state = request.POST.get('state', '').strip()
        user.postal_code = request.POST.get('postal_code', '').strip()
        user.bio = request.POST.get('bio', '').strip()
        
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        try:
            user.save()
            messages.success(request, 'Profile updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
        
        return redirect('users:profile')
    
    # Get user statistics
    from orders.models import Order
    
    orders = Order.objects.filter(user=request.user)
    total_orders = orders.count()
    total_spent = orders.filter(payment_status='paid').aggregate(
        total=Sum('total')
    )['total'] or 0
    
    pending_orders = orders.filter(
        status__in=['pending', 'confirmed', 'preparing', 'out_for_delivery']
    ).count()
    
    context = {
        'user': request.user,
        'profile': profile,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'pending_orders': pending_orders,
    }
    
    return render(request, 'users/profile.html', context)


def polish_demo_view(request):
    """Demo page for polish features."""
    return render(request, 'polish_demo.html')


@login_required
def profile_edit_view(request):
    """Edit profile page."""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update user information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.phone_number = request.POST.get('phone_number', '')
        user.street_address = request.POST.get('street_address', '')
        user.city = request.POST.get('city', '')
        user.state = request.POST.get('state', '')
        user.postal_code = request.POST.get('postal_code', '')
        user.bio = request.POST.get('bio', '')
        
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
        
        user.save()
        
        # Update profile preferences
        profile.email_notifications = request.POST.get('email_notifications') == 'on'
        profile.sms_notifications = request.POST.get('sms_notifications') == 'on'
        profile.push_notifications = request.POST.get('push_notifications') == 'on'
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('users:profile')
    
    context = {
        'user': request.user,
        'profile': profile,
    }
    
    return render(request, 'users/profile_edit.html', context)


@login_required
def change_password_view(request):
    """Change password page."""
    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        new_password2 = request.POST.get('new_password2')
        
        if not request.user.check_password(old_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'users/change_password.html')
        
        if new_password != new_password2:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'users/change_password.html')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'users/change_password.html')
        
        request.user.set_password(new_password)
        request.user.save()
        
        # Re-login user
        login(request, request.user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('users:profile')
    
    return render(request, 'users/change_password.html')


@login_required
def order_history_view(request):
    """User order history page."""
    from orders.models import Order
    
    # Get all orders for user
    orders = Order.objects.filter(
        user=request.user
    ).select_related('restaurant').prefetch_related('items').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get order statistics
    stats = {
        'total': orders.count(),
        'pending': orders.filter(status__in=['pending', 'confirmed', 'preparing']).count(),
        'completed': orders.filter(status='delivered').count(),
        'cancelled': orders.filter(status='cancelled').count(),
    }
    
    context = {
        'orders': page_obj,
        'stats': stats,
        'status_filter': status_filter,
    }
    
    return render(request, 'users/order_history.html', context)


@login_required
def saved_addresses_view(request):
    """Manage saved addresses."""
    # This would typically use a separate Address model
    # For now, we'll use the user's primary address
    
    if request.method == 'POST':
        user = request.user
        user.street_address = request.POST.get('street_address', '')
        user.city = request.POST.get('city', '')
        user.state = request.POST.get('state', '')
        user.postal_code = request.POST.get('postal_code', '')
        user.latitude = request.POST.get('latitude')
        user.longitude = request.POST.get('longitude')
        user.save()
        
        messages.success(request, 'Address updated successfully!')
        return redirect('saved_addresses')
    
    return render(request, 'users/saved_addresses.html')


@login_required
def favorites_view(request):
    """User's favorite restaurants."""
    restaurants = request.user.favorite_restaurants.filter(
        is_active=True
    ).order_by('-average_rating')
    
    context = {
        'restaurants': restaurants,
    }
    
    return render(request, 'users/favorites.html', context)


@login_required
@require_http_methods(["POST"])
def add_favorite(request, restaurant_id):
    """Add restaurant to favorites."""
    from restaurants.models import Restaurant
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    request.user.favorite_restaurants.add(restaurant)
    return JsonResponse({'success': True, 'message': 'Added to favorites'})


@login_required
@require_http_methods(["POST"])
def remove_favorite(request, restaurant_id):
    """Remove restaurant from favorites."""
    from restaurants.models import Restaurant
    restaurant = get_object_or_404(Restaurant, id=restaurant_id)
    request.user.favorite_restaurants.remove(restaurant)
    return JsonResponse({'success': True, 'message': 'Removed from favorites'})


def vendor_dashboard_view(request):
    """Vendor dashboard - moved to restaurants app."""
    from restaurants.views import vendor_dashboard_view as vendor_dashboard
    return vendor_dashboard(request)


# ============ REST API ViewSets ============

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user management.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        # Users can only see their own data
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_profile(self, request):
        """Update current user profile."""
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Password changed successfully.'
            })
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get', 'patch'])
    def profile(self, request):
        """Get or update user profile."""
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        if request.method == 'GET':
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            serializer = UserProfileSerializer(
                profile,
                data=request.data,
                partial=True
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get user statistics."""
        from orders.models import Order
        
        orders = Order.objects.filter(user=request.user)
        
        stats = {
            'total_orders': orders.count(),
            'pending_orders': orders.filter(
                status__in=['pending', 'confirmed', 'preparing', 'out_for_delivery']
            ).count(),
            'completed_orders': orders.filter(status='delivered').count(),
            'cancelled_orders': orders.filter(status='cancelled').count(),
            'total_spent': orders.filter(payment_status='paid').aggregate(
                total=Sum('total')
            )['total'] or 0,
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['delete'])
    def delete_account(self, request):
        """Delete user account."""
        password = request.data.get('password')
        
        if not request.user.check_password(password):
            return Response(
                {'error': 'Invalid password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        user.is_active = False
        user.save()
        
        # In production, you might want to schedule actual deletion
        # after a grace period
        
        return Response({
            'message': 'Account deleted successfully'
        })


class RegisterAPIView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send welcome email
        try:
            from utils.emails import send_welcome_email
            send_welcome_email(user)
        except Exception as e:
            # Don't fail registration if email fails
            print(f"Failed to send welcome email: {e}")
        
        return Response({
            'user': UserSerializer(user).data,
            'message': 'User registered successfully.'
        }, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    """
    API endpoint for user login.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        from django.contrib.auth import authenticate
        from rest_framework_simplejwt.tokens import RefreshToken
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Please provide both username and password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class LogoutAPIView(APIView):
    """
    API endpoint for user logout.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            from rest_framework_simplejwt.tokens import RefreshToken
            
            refresh_token = request.data.get('refresh_token')
            
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            return Response({
                'message': 'Successfully logged out'
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Request password reset email.
    """
    email = request.data.get('email')
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
        
        # Generate reset token
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Send email (implement actual email sending)
        # reset_url = f"{request.build_absolute_uri('/reset-password/')}?uid={uid}&token={token}"
        
        return Response({
            'message': 'Password reset email sent'
        })
        
    except User.DoesNotExist:
        # Don't reveal if email exists
        return Response({
            'message': 'If an account exists with this email, a reset link will be sent.'
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password with token.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_decode
    
    uid = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    if not all([uid, token, new_password]):
        return Response(
            {'error': 'Missing required fields'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user_id = urlsafe_base64_decode(uid).decode()
        user = User.objects.get(pk=user_id)
        
        if default_token_generator.check_token(user, token):
            user.set_password(new_password)
            user.save()
            
            return Response({
                'message': 'Password reset successful'
            })
        else:
            return Response(
                {'error': 'Invalid or expired token'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return Response(
            {'error': 'Invalid reset link'},
            status=status.HTTP_400_BAD_REQUEST
        )