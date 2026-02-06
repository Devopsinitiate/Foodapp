"""
Core models for notification queue and system utilities.
"""
from django.db import models
from django.utils import timezone
import json


class NotificationQueue(models.Model):
    """
    Queue for notifications when Celery is unavailable.
    Provides fallback mechanism for reliable notification delivery.
    """
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('order_created', 'Order Created'),
        ('order_confirmed', 'Order Confirmed'),
        ('order_ready', 'Order Ready'),
        ('order_delivered', 'Order Delivered'),
        ('driver_assigned', 'Driver Assigned'),
        ('delivery_status', 'Delivery Status Update'),
    ]
    
    BACKEND_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
        ('push', 'Push Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Notification details
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default='email')
    
    # Recipient
    recipient = models.CharField(
        max_length=255,
        help_text='Email address, phone number, or user ID'
    )
    recipient_name = models.CharField(max_length=255, blank=True)
    
    # Message content (stored as JSON for flexibility)
    subject = models.CharField(max_length=255, blank=True)
    message_data = models.JSONField(
        default=dict,
        help_text='Message content and template data'
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(
        default=timezone.now,
        help_text='When to send this notification'
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    priority = models.PositiveIntegerField(
        default=5,
        help_text='Lower number = higher priority (1-10)'
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional context (order_id, user_id, etc.)'
    )
    
    class Meta:
        ordering = ['priority', 'scheduled_for', 'created_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_for']),
            models.Index(fields=['notification_type', 'status']),
            models.Index(fields=['backend', 'status']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Notification Queue'
        verbose_name_plural = 'Notification Queue'
    
    def __str__(self):
        return f"{self.get_notification_type_display()} to {self.recipient} ({self.status})"
    
    def mark_processing(self):
        """Mark notification as being processed."""
        self.status = 'processing'
        self.save(update_fields=['status'])
    
    def mark_sent(self):
        """Mark notification as successfully sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_failed(self, error_message):
        """Mark notification as failed and record error."""
        self.status = 'failed'
        self.attempts += 1
        self.error_message = error_message
        self.last_error_at = timezone.now()
        self.save(update_fields=['status', 'attempts', 'error_message', 'last_error_at'])
    
    def should_retry(self):
        """Check if notification should be retried."""
        return self.attempts < self.max_attempts and self.status in ['pending', 'failed']
    
    def get_retry_delay(self):
        """Calculate retry delay with exponential backoff."""
        # 5 min, 15 min, 45 min
        return 5 * (3 ** self.attempts) * 60  # in seconds
    
    @property
    def is_overdue(self):
        """Check if notification is past its scheduled time."""
        return self.scheduled_for <= timezone.now() and self.status == 'pending'


class SystemSetting(models.Model):
    """
    System-wide configuration settings.
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    
    # Type hints
    value_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"{self.key} = {self.value}"
    
    def get_value(self):
        """Get typed value."""
        if self.value_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'integer':
            return int(self.value)
        elif self.value_type == 'json':
            return json.loads(self.value)
        return self.value
    
    @classmethod
    def get_setting(cls, key, default=None):
        """Get a setting value by key."""
        try:
            setting = cls.objects.get(key=key)
            return setting.get_value()
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_setting(cls, key, value, value_type='string', description=''):
        """Set a setting value."""
        if value_type == 'json':
            value = json.dumps(value)
        elif value_type == 'boolean':
            value = str(value)
        elif value_type == 'integer':
            value = str(value)
        
        setting, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': value,
                'value_type': value_type,
                'description': description
            }
        )
        return setting
