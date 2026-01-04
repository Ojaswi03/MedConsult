"""
Payment views for Stripe integration.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.urls import reverse

from apps.scheduling.models import Appointment
from .services import (
    create_checkout_session,
    verify_webhook_signature,
    handle_checkout_completed,
    handle_payment_failed,
    get_payment_for_appointment,
)


@login_required
@require_http_methods(["GET", "POST"])
def checkout(request, appointment_id):
    """
    Create Stripe checkout session and redirect to payment.
    """
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=request.user
    )

    # Check if already paid
    payment = get_payment_for_appointment(appointment)
    if payment and payment.is_paid:
        messages.info(request, 'This appointment has already been paid.')
        return redirect('patient:patient_appointments')

    # Check if slot has a price
    if not appointment.slot.price or appointment.slot.price <= 0:
        messages.info(request, 'This appointment is free. No payment required.')
        return redirect('patient:patient_appointments')

    if request.method == 'POST':
        try:
            # Build success/cancel URLs
            success_url = request.build_absolute_uri(
                reverse('payments:success', kwargs={'appointment_id': appointment.id})
            )
            cancel_url = request.build_absolute_uri(
                reverse('payments:cancel', kwargs={'appointment_id': appointment.id})
            )

            checkout_url, payment = create_checkout_session(
                appointment=appointment,
                success_url=success_url,
                cancel_url=cancel_url,
                request=request
            )

            return redirect(checkout_url)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect('patient:patient_appointments')
        except Exception as e:
            messages.error(request, 'An error occurred while processing payment. Please try again.')
            return redirect('patient:patient_appointments')

    # Show checkout confirmation page
    return render(request, 'payments/checkout.html', {
        'appointment': appointment,
        'payment': payment,
    })


@login_required
def payment_success(request, appointment_id):
    """
    Handle successful payment return from Stripe.
    """
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=request.user
    )

    payment = get_payment_for_appointment(appointment)

    messages.success(request, 'Payment successful! Your appointment has been confirmed.')

    return render(request, 'payments/success.html', {
        'appointment': appointment,
        'payment': payment,
    })


@login_required
def payment_cancel(request, appointment_id):
    """
    Handle cancelled payment return from Stripe.
    """
    appointment = get_object_or_404(
        Appointment,
        id=appointment_id,
        patient=request.user
    )

    messages.warning(request, 'Payment was cancelled. You can try again when ready.')

    return redirect('patient:patient_appointments')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Handle Stripe webhook events.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = verify_webhook_signature(payload, sig_header)
    except ValueError as e:
        return HttpResponse(str(e), status=400)

    # Handle specific events
    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})

    if event_type == 'checkout.session.completed':
        handle_checkout_completed(data)

    elif event_type == 'payment_intent.payment_failed':
        handle_payment_failed(data)

    return HttpResponse(status=200)


@login_required
def payment_history(request):
    """
    Show user's payment history.
    """
    from .models import Payment

    payments = Payment.objects.filter(
        patient=request.user
    ).select_related('appointment', 'appointment__doctor', 'appointment__slot').order_by('-created_at')

    return render(request, 'payments/history.html', {
        'payments': payments,
    })
