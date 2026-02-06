"""
Admin views for driver approval and management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from users.models import User
from delivery.models import DriverAvailability
import os


@staff_member_required
def driver_applications_list(request):
    """List all pending driver applications."""
    status_filter = request.GET.get('status', 'pending')
    
    if status_filter == 'pending':
        drivers = User.objects.filter(
            user_type='driver',
            driver_documents_uploaded=True,
            is_verified_driver=False
        ).order_by('-created_at')
    elif status_filter == 'approved':
        drivers = User.objects.filter(
            user_type='driver',
            is_verified_driver=True
        ).order_by('-created_at')
    else:  # all
        drivers = User.objects.filter(
            user_type='driver'
        ).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(drivers, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'total_pending': User.objects.filter(
            user_type='driver',
            driver_documents_uploaded=True,
            is_verified_driver=False
        ).count(),
        'total_approved': User.objects.filter(
            user_type='driver',
            is_verified_driver=True
        ).count(),
    }
    
    return render(request, 'delivery/admin/driver_applications.html', context)


@staff_member_required
def driver_application_detail(request, driver_id):
    """View detailed information about a driver application."""
    driver = get_object_or_404(User, id=driver_id, user_type='driver')
    
    # Get uploaded documents
    documents_folder = f'media/driver_documents/{driver.id}/'
    documents = {}
    
    if os.path.exists(documents_folder):
        for filename in os.listdir(documents_folder):
            if filename.startswith('license_'):
                documents['license'] = f'/media/driver_documents/{driver.id}/{filename}'
            elif filename.startswith('registration_'):
                documents['registration'] = f'/media/driver_documents/{driver.id}/{filename}'
            elif filename.startswith('insurance_'):
                documents['insurance'] = f'/media/driver_documents/{driver.id}/{filename}'
    
    # Get or create driver availability record
    availability, created = DriverAvailability.objects.get_or_create(driver=driver)
    
    context = {
        'driver': driver,
        'documents': documents,
        'availability': availability,
    }
    
    return render(request, 'delivery/admin/driver_detail.html', context)


@staff_member_required
def approve_driver(request, driver_id):
    """Approve a driver application."""
    if request.method != 'POST':
        return redirect('delivery:admin_driver_applications')
    
    driver = get_object_or_404(User, id=driver_id, user_type='driver')
    
    # Approve driver
    driver.is_verified_driver = True
    driver.save()
    
    # Send approval email (optional - can be implemented later)
    # send_driver_approval_email(driver)
    
    messages.success(
        request,
        f'Driver {driver.get_full_name()} has been approved and can now go online!'
    )
    
    return redirect('delivery:admin_driver_detail', driver_id=driver_id)


@staff_member_required
def reject_driver(request, driver_id):
    """Reject a driver application."""
    if request.method != 'POST':
        return redirect('delivery:admin_driver_applications')
    
    driver = get_object_or_404(User, id=driver_id, user_type='driver')
    reason = request.POST.get('reason', 'Application does not meet requirements')
    
    # Mark as rejected (you might want to add a rejection field to User model)
    driver.is_verified_driver = False
    driver.driver_documents_uploaded = False  # Require re-upload
    driver.save()
    
    # Send rejection email with reason (optional)
    # send_driver_rejection_email(driver, reason)
    
    messages.warning(
        request,
        f'Driver {driver.get_full_name()} has been rejected. Reason: {reason}'
    )
    
    return redirect('delivery:admin_driver_applications')


@staff_member_required
def deactivate_driver(request, driver_id):
    """Deactivate an approved driver."""
    if request.method != 'POST':
        return redirect('delivery:admin_driver_applications')
    
    driver = get_object_or_404(User, id=driver_id, user_type='driver')
    reason = request.POST.get('reason', 'Account deactivated by admin')
    
    # Deactivate driver
    driver.is_verified_driver = False
    driver.is_active = False
    driver.save()
    
    # Set driver offline
    try:
        availability = DriverAvailability.objects.get(driver=driver)
        availability.go_offline()
    except DriverAvailability.DoesNotExist:
        pass
    
    messages.warning(
        request,
        f'Driver {driver.get_full_name()} has been deactivated. Reason: {reason}'
    )
    
    return redirect('delivery:admin_driver_detail', driver_id=driver_id)


@staff_member_required
def manual_assignment_view(request):
    """View for manually assigning deliveries to drivers."""
    from delivery.models import Delivery
    from django.utils import timezone
    
    # Get unassigned deliveries  
    unassigned_deliveries = Delivery.objects.filter(
        status='pending',
        driver__isnull=True
    ).select_related('order', 'order__restaurant').order_by('-created_at')
    
    # Get active deliveries
    active_deliveries = Delivery.objects.filter(
        status__in=['assigned', 'accepted', 'picked_up', 'en_route']
    ).select_related('order', 'order__restaurant', 'driver').order_by('-assigned_at')
    
    # Get available drivers
    available_drivers = User.objects.filter(
        user_type='driver',
        is_verified_driver=True,
        is_active=True
    ).select_related('availability').order_by('first_name')
    
    # Filter to only those with availability records
    available_drivers = [
        d for d in available_drivers 
        if hasattr(d, 'availability')
    ]
    
    context = {
        'unassigned_deliveries': unassigned_deliveries,
        'active_deliveries': active_deliveries,
        'available_drivers': available_drivers,
    }
    
    return render(request, 'delivery/admin/manual_assignment.html', context)


@staff_member_required
def assign_driver_manually(request, delivery_id):
    """Manually assign a driver to a delivery."""
    from delivery.models import Delivery
    from django.utils import timezone
    
    if request.method != 'POST':
        return redirect('delivery:admin_manual_assignment')
    
    delivery = get_object_or_404(Delivery, id=delivery_id)
    driver_id = request.POST.get('driver_id')
    
    if not driver_id:
        messages.error(request, 'Please select a driver')
        return redirect('delivery:admin_manual_assignment')
    
    driver = get_object_or_404(User, id=driver_id, user_type='driver', is_verified_driver=True)
    
    # Assign driver
    delivery.driver = driver
    delivery.status = 'assigned'
    delivery.assigned_at = timezone.now()
    delivery.save()
    
    # Mark driver as busy
    try:
        availability = DriverAvailability.objects.get(driver=driver)
        availability.is_available = False
        availability.save()
    except DriverAvailability.DoesNotExist:
        pass
    
    # Update order status
    delivery.order.status = 'confirmed'
    delivery.order.save()
    
    messages.success(
        request,
        f'Delivery #{delivery.order.order_number} assigned to {driver.get_full_name()}'
    )
    
    return redirect('delivery:admin_manual_assignment')
