"""
Video consultation models.
"""
from django.db import models


class VideoRoom(models.Model):
    """Video room for an appointment consultation."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('ended', 'Ended'),
    ]

    appointment = models.OneToOneField(
        'scheduling.Appointment',
        on_delete=models.CASCADE,
        related_name='video_room'
    )
    daily_room_name = models.CharField(max_length=255, unique=True)
    daily_room_url = models.URLField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = 'video_rooms'
        ordering = ['-created_at']

    def __str__(self):
        return f"Video Room for Appointment #{self.appointment.id}"

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def can_join(self):
        return self.status in ['pending', 'active']
