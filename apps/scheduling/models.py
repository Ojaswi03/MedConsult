from django.db import models
from django.utils import timezone
from apps.accounts.models import User, DoctorProfile


class AvailabilityWindow(models.Model):
    """
    Recurring availability for doctors (e.g., "Every Monday 9-5").
    Slots are generated from these windows.
    """
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='availability_windows')
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'availability_windows'
        ordering = ['weekday', 'start_time']

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class Slot(models.Model):
    """
    Generated time slots from availability windows.
    Single source of truth for available times.
    """
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='slots')
    availability_window = models.ForeignKey(
        AvailabilityWindow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_slots'
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    is_booked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'slots'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['doctor', 'start_datetime']),
            models.Index(fields=['is_booked', 'start_datetime']),
        ]

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    def is_available(self):
        """Check if slot is available for booking."""
        return not self.is_booked and self.start_datetime > timezone.now()


class Appointment(models.Model):
    """
    Appointment between patient and doctor.
    References a specific slot (single source of truth).
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    slot = models.OneToOneField(Slot, on_delete=models.PROTECT, related_name='appointment')
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_appointments')
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='doctor_appointments')
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointments'
        ordering = ['-slot__start_datetime']
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['doctor', 'status']),
        ]

    def __str__(self):
        return f"{self.patient.get_display_name()} with Dr. {self.doctor.user.get_display_name()} on {self.slot.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    @property
    def start_datetime(self):
        """Convenience property to get appointment start time."""
        return self.slot.start_datetime

    @property
    def end_datetime(self):
        """Convenience property to get appointment end time."""
        return self.slot.end_datetime

    def can_cancel(self):
        """Check if appointment can be cancelled."""
        return self.status == 'scheduled' and self.start_datetime > timezone.now()
