"""
Review-related views for submitting and managing reviews.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from restaurants.models import Restaurant, Review
from restaurants.forms import ReviewForm, VendorResponseForm
from orders.models import Order


@login_required
def submit_review_view(request, order_number):
    """
    Submit a review for a delivered order.
    """
    # Get the order and verify it belongs to the user
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    
    # Verify order is delivered
    if order.status != 'delivered':
        messages.error(request, 'You can only review delivered orders.')
        return redirect('orders:detail', order_number=order_number)
    
    # Check if review already exists
    existing_review = Review.objects.filter(
        restaurant=order.restaurant,
        user=request.user,
        order=order
    ).first()
    
    if existing_review:
        messages.info(request, 'You have already reviewed this order.')
        return redirect('orders:detail', order_number=order_number)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.restaurant = order.restaurant
            review.order = order
            review.is_verified_purchase = True
            review.save()
            
            messages.success(request, 'Thank you for your review!')
            
            # Send email to vendor (optional)
            try:
                from utils.emails import send_html_email
                send_html_email(
                    subject=f"New Review for {order.restaurant.name}",
                    template_name="emails/vendor_new_review.html",
                    context={'review': review, 'restaurant': order.restaurant},
                    recipient_list=[order.restaurant.owner.email]
                )
            except Exception as e:
                print(f"Failed to send review notification: {e}")
            
            return redirect('restaurants:detail', slug=order.restaurant.slug)
    else:
        form = ReviewForm()
    
    context = {
        'form': form,
        'order': order,
        'restaurant': order.restaurant,
    }
    return render(request, 'restaurants/submit_review.html', context)


@login_required
def vendor_respond_to_review(request, review_id):
    """
    Vendor responds to a review.
    """
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('home')
    
    # Get review and verify vendor owns the restaurant
    review = get_object_or_404(Review, id=review_id)
    
    if review.restaurant.owner != request.user:
        messages.error(request, 'You can only respond to reviews for your restaurants.')
        return redirect('vendors:dashboard')
    
    if request.method == 'POST':
        form = VendorResponseForm(request.POST, instance=review)
        if form.is_valid():
            review = form.save(commit=False)
            review.vendor_response_date = timezone.now()
            review.save()
            
            messages.success(request, 'Your response has been posted.')
            
            # Send email to customer (optional)
            try:
                from utils.emails import send_html_email
                send_html_email(
                    subject=f"{review.restaurant.name} Responded to Your Review",
                    template_name="emails/vendor_response_notification.html",
                    context={'review': review},
                    recipient_list=[review.user.email]
                )
            except Exception as e:
                print(f"Failed to send response notification: {e}")
            
            return redirect('vendors:manage_reviews')
    else:
        form = VendorResponseForm(instance=review)
    
    context = {
        'form': form,
        'review': review,
    }
    return render(request, 'vendors/respond_to_review.html', context)


@login_required
def vendor_manage_reviews(request):
    """
    Vendor view to manage all reviews for their restaurants.
    """
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('home')
    
    restaurants = Restaurant.objects.filter(owner=request.user)
    reviews = Review.objects.filter(
        restaurant__in=restaurants,
        is_approved=True
    ).select_related('user', 'restaurant', 'order').order_by('-created_at')
    
    # Filter options
    filter_status = request.GET.get('filter', 'all')
    if filter_status == 'pending_response':
        reviews = reviews.filter(vendor_response__isnull=True)
    elif filter_status == 'responded':
        reviews = reviews.filter(vendor_response__isnull=False)
    
    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(reviews, 20)
    page_number = request.GET.get('page')
    reviews_page = paginator.get_page(page_number)
    
    context = {
        'reviews': reviews_page,
        'filter_status': filter_status,
    }
    return render(request, 'vendors/manage_reviews.html', context)
