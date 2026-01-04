"""
Payment models for MedConsult.
"""
from django.db import models
from django.conf import settings


class Payment(models.Model):
    """Payment record for an appointment."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]

    appointment = models.OneToOneField(
        'scheduling.Appointment',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - {self.amount} {self.currency} ({self.status})"

    @property
    def amount_in_cents(self):
        """Return amount in cents for Stripe."""
        return int(self.amount * 100)

    @property
    def is_paid(self):
        return self.status == 'succeeded'

    @property
    def can_refund(self):
        return self.status in ['succeeded', 'partially_refunded']


class Refund(models.Model):
    """Refund record for a payment."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
    ]

    REASON_CHOICES = [
        ('requested_by_customer', 'Requested by Customer'),
        ('duplicate', 'Duplicate'),
        ('fraudulent', 'Fraudulent'),
        ('appointment_cancelled', 'Appointment Cancelled'),
        ('other', 'Other'),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='refunds'
    )
    stripe_refund_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, default='other')
    reason_text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )

    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']

    def __str__(self):
        return f"Refund {self.id} - {self.amount} {self.payment.currency}"

    @property
    def amount_in_cents(self):
        """Return amount in cents for Stripe."""
        return int(self.amount * 100)
