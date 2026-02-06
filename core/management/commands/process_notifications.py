"""
Management command to process notification queue.
Run via: python manage.py process_notifications
Can be scheduled via cron when Celery is unavailable.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import NotificationQueue
from core.utils.notification_sender import send_notification
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process pending notifications in the queue'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of notifications to process in one run'
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Also retry failed notifications'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up old sent notifications (>30 days)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually sending'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        retry_failed = options['retry_failed']
        cleanup = options['cleanup']
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('Starting notification processing...'))
        
        results = {
            'pending_processed': 0,
            'pending_sent': 0,
            'pending_failed': 0,
            'failed_retried': 0,
            'failed_sent': 0,
            'cleaned_up': 0
        }
        
        # Process pending notifications
        pending = NotificationQueue.objects.filter(
            status='pending',
            scheduled_for__lte=timezone.now()
        ).order_by('priority', 'scheduled_for')[:batch_size]
        
        self.stdout.write(f'Found {pending.count()} pending notifications')
        
        for notification in pending:
            results['pending_processed'] += 1
            
            if dry_run:
                self.stdout.write(
                    f'  [DRY RUN] Would send: {notification.notification_type} '
                    f'to {notification.recipient}'
                )
                continue
            
            if not notification.should_retry():
                self.stdout.write(
                    self.style.WARNING(
                        f'  Skipping {notification.id} - max attempts reached'
                    )
                )
                continue
            
            self.stdout.write(f'  Processing {notification.id}...')
            
            try:
                result = send_notification(notification)
                
                if result['success']:
                    results['pending_sent'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'    ✓ Sent successfully')
                    )
                else:
                    results['pending_failed'] += 1
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Failed: {result["message"]}')
                    )
                    
            except Exception as e:
                results['pending_failed'] += 1
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Error: {e}')
                )
        
        # Retry failed notifications if requested
        if retry_failed:
            self.stdout.write('\nRetrying failed notifications...')
            
            failed = NotificationQueue.objects.filter(
                status='failed'
            ).order_by('last_error_at')[:20]
            
            for notification in failed:
                if not notification.should_retry():
                    continue
                
                # Check retry delay
                if notification.last_error_at:
                    retry_delay = notification.get_retry_delay()
                    time_since_failure = (
                        timezone.now() - notification.last_error_at
                    ).total_seconds()
                    
                    if time_since_failure < retry_delay:
                        continue
                
                results['failed_retried'] += 1
                
                if dry_run:
                    self.stdout.write(
                        f'  [DRY RUN] Would retry: {notification.id}'
                    )
                    continue
                
                notification.status = 'pending'
                notification.save(update_fields=['status'])
                
                result = send_notification(notification)
                
                if result['success']:
                    results['failed_sent'] += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Retry successful: {notification.id}')
                    )
        
        # Cleanup old notifications if requested
        if cleanup and not dry_run:
            self.stdout.write('\nCleaning up old notifications...')
            
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=30)
            
            deleted, _ = NotificationQueue.objects.filter(
                status='sent',
                sent_at__lt=cutoff
            ).delete()
            
            results['cleaned_up'] = deleted
            self.stdout.write(
                self.style.SUCCESS(f'  Deleted {deleted} old notifications')
            )
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS('SUMMARY:'))
        self.stdout.write(f'  Pending processed: {results["pending_processed"]}')
        self.stdout.write(f'  Pending sent: {results["pending_sent"]}')
        self.stdout.write(f'  Pending failed: {results["pending_failed"]}')
        
        if retry_failed:
            self.stdout.write(f'  Failed retried: {results["failed_retried"]}')
            self.stdout.write(f'  Failed sent: {results["failed_sent"]}')
        
        if cleanup:
            self.stdout.write(f'  Cleaned up: {results["cleaned_up"]}')
        
        self.stdout.write('='*50)
        self.stdout.write(self.style.SUCCESS('Done!'))
