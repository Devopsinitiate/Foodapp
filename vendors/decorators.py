"""
Decorators for vendor views.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required


def vendor_required(view_func):
    """
    Decorator to require vendor user type and active vendor status.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_vendor:
            messages.error(request, 'Access denied. Vendor account required.')
            return redirect('home')
        
        if not request.user.is_active_vendor:
            messages.warning(request, 'Your vendor account is pending approval.')
            return redirect('vendors:pending')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def vendor_or_admin_required(view_func):
    """
    Decorator to require vendor or admin user type.
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_vendor or request.user.is_staff):
            messages.error(request, 'Access denied.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
