"""
Messaging models for in-app chat.
"""
from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """Conversation between patient and doctor, optionally linked to an appointment."""

    appointment = models.OneToOneField(
        'scheduling.Appointment',
        on_delete=models.CASCADE,
        related_name='conversation',
        null=True,
        blank=True,
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='patient_conversations'
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doctor_conversations'
    )
    is_direct = models.BooleanField(
        default=False,
        help_text='True when started without a scheduled appointment'
    )
    is_active = models.BooleanField(default=True)
    deleted_by_patient = models.BooleanField(default=False)
    deleted_by_doctor = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'conversations'
        ordering = ['-last_message_at', '-created_at']

    def __str__(self):
        if self.appointment_id:
            return f"Conversation for Appointment #{self.appointment_id}"
        return f"Direct conversation between {self.patient} and {self.doctor}"

    def get_other_participant(self, user):
        """Get the other participant in the conversation."""
        if user.id == self.patient.id:
            return self.doctor
        return self.patient

    def unread_count_for_user(self, user):
        """Get count of unread messages for a user."""
        return self.messages.filter(is_read=False).exclude(sender=user).count()


class Message(models.Model):
    """Individual message in a conversation."""

    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('system', 'System'),
        ('file', 'File Attachment'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(
        upload_to='message_attachments/',
        blank=True,
        null=True,
        help_text='Optional file attachment'
    )
    attachment_name = models.CharField(max_length=255, blank=True, help_text='Original filename for display')

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.get_display_name()} at {self.created_at}"
