from django.db import models
from apps.accounts.models import User


class AdminActivityLog(models.Model):
    """Track admin actions for audit trail and compliance."""

    ACTION_TYPES = [
        ('doctor_verified', 'Doctor Verified'),
        ('doctor_rejected', 'Doctor Rejected'),
        ('user_activated', 'User Activated'),
        ('user_deactivated', 'User Deactivated'),
        ('user_viewed', 'User Viewed'),
        ('document_viewed', 'Document Viewed'),
        ('export_created', 'Export Created'),
        ('settings_changed', 'Settings Changed'),
        ('bulk_verify', 'Bulk Doctor Verify'),
        ('bulk_reject', 'Bulk Doctor Reject'),
        ('slot_created', 'Slot Created'),
        ('slot_blocked', 'Slot Blocked'),
        ('slot_unblocked', 'Slot Unblocked'),
        ('slot_deleted', 'Slot Deleted'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('refund_processed', 'Refund Processed'),
    ]

    admin = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_actions'
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='actions_received'
    )
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    organization = models.ForeignKey(
        'accounts.Organization', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='admin_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'admin_activity_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
        ]
        verbose_name = 'Admin Activity Log'
        verbose_name_plural = 'Admin Activity Logs'

    def __str__(self):
        admin_name = self.admin.get_display_name() if self.admin else 'Unknown'
        return f"{admin_name} - {self.get_action_type_display()} - {self.created_at}"


class HealthRecordAccessLog(models.Model):
    """Audit trail for health record access — required for HIPAA compliance."""
    ACCESS_TYPES = [
        ('viewed', 'Viewed'),
        ('downloaded', 'Downloaded'),
        ('shared', 'Shared'),
        ('unshared', 'Unshared'),
    ]
    record = models.ForeignKey(
        'scheduling.HealthRecord',
        on_delete=models.CASCADE,
        related_name='access_logs'
    )
    accessed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='health_record_access_logs'
    )
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    organization = models.ForeignKey(
        'accounts.Organization', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='health_record_access_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'health_record_access_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['record', 'created_at']),
            models.Index(fields=['accessed_by', 'created_at']),
        ]

    def __str__(self):
        user = self.accessed_by.get_display_name() if self.accessed_by else 'Unknown'
        return f"{user} {self.access_type} record #{self.record_id} at {self.created_at}"
