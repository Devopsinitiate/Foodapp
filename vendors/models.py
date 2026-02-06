"""
Vendor management models.
"""
from django.db import models
from django.core.validators import MinValueValidator
from users.models import User


class VendorProfile(models.Model):
    """
    Extended profile for vendor users.
    Stores business information and application details.
    """
    APPLICATION_STATUS = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='vendor_profile'
    )
    
    # Business Information
    business_name = models.CharField(max_length=200)
    business_type = models.CharField(
        max_length=50,
        choices=[
            ('restaurant', 'Restaurant'),
            ('cafe', 'Cafe'),
            ('fast_food', 'Fast Food'),
            ('bakery', 'Bakery'),
            ('food_truck', 'Food Truck'),
            ('catering', 'Catering Service'),
        ],
        default='restaurant'
    )
    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Business registration or tax ID'
    )
    
    # Bank Details (for payouts)
    bank_account_name = models.CharField(max_length=200)
    bank_account_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=20, blank=True)
    
    # Application Status
    application_status = models.CharField(
        max_length=20,
        choices=APPLICATION_STATUS,
        default='pending'
    )
    application_date = models.DateTimeField(auto_now_add=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_vendors'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Additional Information
    years_of_experience = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField(
        blank=True,
        help_text='Tell us about your business'
    )
    
    # Documents
    business_license = models.FileField(
        upload_to='vendor_documents/licenses/',
        null=True,
        blank=True
    )
    health_certificate = models.FileField(
        upload_to='vendor_documents/certificates/',
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Vendor Profile'
        verbose_name_plural = 'Vendor Profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business_name} - {self.user.username}"
    
    @property
    def is_approved(self):
        return self.application_status == 'approved'
    
    @property
    def is_pending(self):
        return self.application_status == 'pending'
    
    @property
    def is_rejected(self):
        return self.application_status == 'rejected'
    
    def save(self, *args, **kwargs):
        """Override save to automatically update user status."""
        # Check if status changed
        if self.pk:
            old_instance = VendorProfile.objects.get(pk=self.pk)
            if old_instance.application_status != self.application_status:
                # Status changed, update user accordingly
                if self.application_status == 'approved':
                    self.user.is_active_vendor = True
                    self.user.user_type = 'vendor'
                    self.user.save(update_fields=['is_active_vendor', 'user_type'])
                else:
                    self.user.is_active_vendor = False
                    self.user.save(update_fields=['is_active_vendor'])
        
        super().save(*args, **kwargs)
    
    def approve(self, approved_by_user):
        """Approve vendor application."""
        from django.utils import timezone
        self.application_status = 'approved'
        self.approval_date = timezone.now()
        self.approved_by = approved_by_user
        self.save()
        
        # Update user status (handled in save method now)
        self.user.is_active_vendor = True
        self.user.user_type = 'vendor'
        self.user.save(update_fields=['is_active_vendor', 'user_type'])
        
        # Send approval email
        from users.emails import send_vendor_approval_email
        send_vendor_approval_email(self)
    
    def reject(self, reason):
        """Reject vendor application."""
        self.application_status = 'rejected'
        self.rejection_reason = reason
        self.save()
        
        # Update user status (handled in save method now)
        self.user.is_active_vendor = False
        self.user.save(update_fields=['is_active_vendor'])
        
        # Send rejection email
        from users.emails import send_vendor_rejection_email
        send_vendor_rejection_email(self)
