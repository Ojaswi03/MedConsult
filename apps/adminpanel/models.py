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
