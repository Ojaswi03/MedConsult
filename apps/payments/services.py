"""
Payment services for Stripe integration.
"""
import stripe
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from .models import Payment, Refund


def get_stripe_client():
    """Get configured Stripe client."""
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@transaction.atomic
def create_checkout_session(appointment, success_url, cancel_url, request=None):
    """
    Create a Stripe Checkout session for an appointment.

    Returns: (checkout_url, payment)
    """
    stripe_client = get_stripe_client()

    # Get appointment price from slot
    slot = appointment.slot
    amount = slot.price or Decimal('0.00')

    if amount <= 0:
        raise ValueError("Cannot create checkout for free appointments")

    # Create or get payment record
    payment, created = Payment.objects.get_or_create(
        appointment=appointment,
        defaults={
            'patient': appointment.patient,
            'amount': amount,
            'status': 'pending',
            'description': f"Consultation with Dr. {appointment.doctor.user.get_display_name()}",
        }
    )

    if not created and payment.status == 'succeeded':
        raise ValueError("This appointment has already been paid for")

    # Create Stripe Checkout Session
    try:
        checkout_session = stripe_client.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{slot.get_appointment_type_display()} Consultation',
                        'description': f"Appointment with Dr. {appointment.doctor.user.get_display_name()} on {appointment.start_datetime.strftime('%B %d, %Y at %I:%M %p')}",
                    },
                    'unit_amount': payment.amount_in_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=appointment.patient.email,
            metadata={
                'appointment_id': str(appointment.id),
                'payment_id': str(payment.id),
                'doctor_id': str(appointment.doctor.id),
                'patient_id': str(appointment.patient.id),
            },
        )

        # Update payment with session ID
        payment.stripe_checkout_session_id = checkout_session.id
        payment.status = 'processing'
        payment.save()

        return checkout_session.url, payment

    except stripe.error.StripeError as e:
        payment.status = 'failed'
        payment.metadata['error'] = str(e)
        payment.save()
        raise


def handle_checkout_completed(session):
    """
    Handle successful checkout session completion from webhook.
    """
    payment_id = session.get('metadata', {}).get('payment_id')
    if not payment_id:
        return None

    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return None

    if payment.status == 'succeeded':
        return payment  # Already processed

    payment.stripe_payment_intent_id = session.get('payment_intent')
    payment.status = 'succeeded'
    payment.paid_at = timezone.now()
    payment.save()

    # Update appointment status if needed
    appointment = payment.appointment
    if hasattr(appointment, 'payment_status'):
        appointment.payment_status = 'paid'
        appointment.save(update_fields=['payment_status'])

    return payment


def handle_payment_failed(session):
    """
    Handle failed payment from webhook.
    """
    payment_id = session.get('metadata', {}).get('payment_id')
    if not payment_id:
        return None

    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return None

    payment.status = 'failed'
    payment.save()

    return payment


@transaction.atomic
def create_refund(payment, amount=None, reason='other', reason_text='', processed_by=None):
    """
    Create a refund for a payment.

    Args:
        payment: Payment object to refund
        amount: Amount to refund (None for full refund)
        reason: Reason code for refund
        reason_text: Additional explanation
        processed_by: User who initiated the refund
    """
    if not payment.can_refund:
        raise ValueError("This payment cannot be refunded")

    if not payment.stripe_payment_intent_id:
        raise ValueError("No Stripe payment intent found")

    stripe_client = get_stripe_client()

    # Default to full refund
    if amount is None:
        amount = payment.amount

    # Validate refund amount
    total_refunded = sum(r.amount for r in payment.refunds.filter(status='succeeded'))
    remaining = payment.amount - total_refunded

    if amount > remaining:
        raise ValueError(f"Refund amount ({amount}) exceeds remaining refundable amount ({remaining})")

    # Create refund record
    refund = Refund.objects.create(
        payment=payment,
        amount=amount,
        reason=reason,
        reason_text=reason_text,
        status='pending',
        processed_by=processed_by,
    )

    try:
        # Create Stripe refund
        stripe_refund = stripe_client.Refund.create(
            payment_intent=payment.stripe_payment_intent_id,
            amount=refund.amount_in_cents,
            reason=reason if reason in ['duplicate', 'fraudulent', 'requested_by_customer'] else None,
        )

        refund.stripe_refund_id = stripe_refund.id
        refund.status = 'succeeded'
        refund.processed_at = timezone.now()
        refund.save()

        # Update payment status
        total_refunded = sum(r.amount for r in payment.refunds.filter(status='succeeded'))
        if total_refunded >= payment.amount:
            payment.status = 'refunded'
        else:
            payment.status = 'partially_refunded'
        payment.save()

        return refund

    except stripe.error.StripeError as e:
        refund.status = 'failed'
        refund.save()
        raise


def verify_webhook_signature(payload, sig_header):
    """
    Verify Stripe webhook signature.
    Returns the event if valid, raises error otherwise.
    """
    stripe_client = get_stripe_client()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except ValueError as e:
        raise ValueError(f"Invalid payload: {e}")
    except stripe.error.SignatureVerificationError as e:
        raise ValueError(f"Invalid signature: {e}")


def get_payment_for_appointment(appointment):
    """Get payment record for an appointment."""
    try:
        return Payment.objects.get(appointment=appointment)
    except Payment.DoesNotExist:
        return None
