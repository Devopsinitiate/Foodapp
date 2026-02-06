"""
Admin configuration for vendors app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import VendorProfile


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    """Admin interface for VendorProfile."""
    
    list_display = [
        'business_name',
        'user',
        'business_type',
        'application_status_badge',
        'application_date',
        'approval_date',
    ]
    
    list_filter = [
        'application_status',
        'business_type',
        'application_date',
    ]
    
    search_fields = [
        'business_name',
        'user__username',
        'user__email',
        'bank_account_name',
    ]
    
    readonly_fields = [
        'application_date',
        'created_at',
        'updated_at',
    ]
    
    fieldsets = (
        ('Business Information', {
            'fields': (
                'user',
                'business_name',
                'business_type',
                'business_registration_number',
                'years_of_experience',
                'description',
            )
        }),
        ('Bank Details', {
            'fields': (
                'bank_account_name',
                'bank_account_number',
                'bank_name',
                'bank_code',
            )
        }),
        ('Application Status', {
            'fields': (
                'application_status',
                'application_date',
                'approval_date',
                'approved_by',
                'rejection_reason',
            )
        }),
        ('Documents', {
            'fields': (
                'business_license',
                'health_certificate',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_vendors', 'reject_vendors']
    
    def application_status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
        }
        color = colors.get(obj.application_status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_application_status_display()
        )
    application_status_badge.short_description = 'Status'
    
    def approve_vendors(self, request, queryset):
        """Bulk approve vendors."""
        count = 0
        for vendor in queryset.filter(application_status='pending'):
            vendor.approve(request.user)
            count += 1
        self.message_user(request, f'{count} vendor(s) approved successfully.')
    approve_vendors.short_description = 'Approve selected vendors'
    
    def reject_vendors(self, request, queryset):
        """Bulk reject vendors."""
        count = 0
        for vendor in queryset.filter(application_status='pending'):
            vendor.reject('Rejected by admin')
            count += 1
        self.message_user(request, f'{count} vendor(s) rejected.')
    reject_vendors.short_description = 'Reject selected vendors'
