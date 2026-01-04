from django.db import models
from django.utils import timezone
from apps.accounts.models import User, DoctorProfile


# Appointment type choices used across models
APPOINTMENT_TYPE_CHOICES = [
    ('video', 'Video Consultation'),
    ('chat', 'Chat Consultation'),
    ('phone', 'Phone Consultation'),
]


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

    # New fields for enhanced availability management
    buffer_before_minutes = models.IntegerField(default=0, help_text='Buffer time before appointment in minutes')
    buffer_after_minutes = models.IntegerField(default=0, help_text='Buffer time after appointment in minutes')
    is_recurring = models.BooleanField(default=True, help_text='Whether this window repeats weekly')
    effective_date = models.DateField(null=True, blank=True, help_text='Start date for non-recurring or effective start')
    end_date = models.DateField(null=True, blank=True, help_text='End date for recurring windows')
    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
        default='video',
        help_text='Default appointment type for slots generated from this window'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'availability_windows'
        ordering = ['weekday', 'start_time']

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"


class AvailabilityWindowTypeConfig(models.Model):
    """
    Links availability windows to appointment types with inline pricing.
    Allows doctors to offer multiple consultation types for the same time window.
    """
    window = models.ForeignKey(
        AvailabilityWindow,
        on_delete=models.CASCADE,
        related_name='type_configs'
    )
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'availability_window_type_configs'
        unique_together = ['window', 'appointment_type']
        ordering = ['appointment_type']

    def __str__(self):
        return f"{self.window} - {self.get_appointment_type_display()} (${self.price})"


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

    # New fields for enhanced slot management
    appointment_type = models.CharField(
        max_length=20,
        choices=APPOINTMENT_TYPE_CHOICES,
        default='video'
    )
    max_capacity = models.IntegerField(default=1, help_text='Max patients for group sessions')
    current_bookings = models.IntegerField(default=0, help_text='Current number of bookings')
    is_urgent = models.BooleanField(default=False, help_text='Manually created urgent slot')
    is_blocked = models.BooleanField(default=False, help_text='Blocked for time off')
    notes = models.CharField(max_length=255, blank=True, help_text='Doctor notes for this slot')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'slots'
        ordering = ['start_datetime']
        indexes = [
            models.Index(fields=['doctor', 'start_datetime']),
            models.Index(fields=['is_booked', 'start_datetime']),
            models.Index(fields=['is_blocked', 'start_datetime']),
        ]

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    def is_available(self):
        """Check if slot is available for booking."""
        if self.is_blocked:
            return False
        if self.max_capacity > 1:
            # Group session: available if not at capacity
            return self.current_bookings < self.max_capacity and self.start_datetime > timezone.now()
        # Standard slot: available if not booked
        return not self.is_booked and self.start_datetime > timezone.now()

    def get_status(self):
        """Get slot status for calendar display."""
        if self.is_blocked:
            return 'blocked'
        if self.is_booked or (self.max_capacity > 1 and self.current_bookings >= self.max_capacity):
            return 'booked'
        if self.is_urgent:
            return 'urgent'
        if hasattr(self, 'appointment') and self.appointment.status == 'scheduled':
            return 'pending'
        return 'available'

    def get_price(self):
        """Get the price for this slot based on its appointment type and availability window."""
        from decimal import Decimal

        # If slot has an availability window, check type configs
        if self.availability_window:
            type_config = self.availability_window.type_configs.filter(
                appointment_type=self.appointment_type,
                is_enabled=True
            ).first()

            if type_config:
                return type_config.price

        # Fallback to doctor's default consultation fee
        return self.doctor.consultation_fee if hasattr(self.doctor, 'consultation_fee') else Decimal('0')


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


class AppointmentTypeConfig(models.Model):
    """
    Configuration for different appointment types per doctor.
    Allows doctors to set pricing and enable/disable types.
    """
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='appointment_type_configs'
    )
    appointment_type = models.CharField(max_length=20, choices=APPOINTMENT_TYPE_CHOICES)
    duration_minutes = models.IntegerField(default=30)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'appointment_type_configs'
        unique_together = ['doctor', 'appointment_type']
        ordering = ['appointment_type']

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.get_appointment_type_display()} (${self.price})"


class SlotChangeLog(models.Model):
    """
    Tracks slot changes for real-time notification to patients.
    Used by HTMX polling to detect updates.
    """
    CHANGE_TYPES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('booked', 'Booked'),
        ('cancelled', 'Cancelled'),
    ]

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name='slot_changes'
    )
    slot = models.ForeignKey(
        Slot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='change_logs'
    )
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'slot_change_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['doctor', 'created_at']),
        ]

    def __str__(self):
        return f"{self.doctor.user.get_display_name()} - {self.change_type} at {self.created_at}"
