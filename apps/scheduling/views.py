from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from datetime import timedelta

from apps.accounts.models import DoctorProfile
from apps.accounts.selectors import get_all_verified_doctors
from .models import Slot, Appointment, AvailabilityWindow
from .services import book_appointment, cancel_appointment, generate_slots_for_doctor
from .selectors import (
    get_available_slots_for_doctor,
    get_patient_appointments,
    get_doctor_appointments,
    get_doctor_availability_windows,
    get_upcoming_doctor_appointments
)


# ========== PATIENT VIEWS ==========

@login_required
def patient_doctors_list(request):
    """Patient view: List all verified doctors."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    doctors = get_all_verified_doctors()
    return render(request, 'scheduling/patient/doctors_list.html', {'doctors': doctors})


@login_required
def patient_doctor_detail(request, doctor_id):
    """Patient view: Doctor detail page with available slots."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id, verification_status='verified')

    # Get available slots for the next 14 days
    available_slots = get_available_slots_for_doctor(doctor)[:50]  # Limit to 50 slots

    return render(request, 'scheduling/patient/doctor_detail.html', {
        'doctor': doctor,
        'available_slots': available_slots
    })


@login_required
def patient_book_appointment(request, slot_id):
    """Patient view: Book an appointment."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    slot = get_object_or_404(Slot, id=slot_id)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        try:
            appointment = book_appointment(slot, request.user, reason)
            messages.success(request, 'Appointment booked successfully!')
            return redirect('patient:patient_appointments')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('patient:doctor_detail', doctor_id=slot.doctor.id)

    return render(request, 'scheduling/patient/book.html', {'slot': slot})


@login_required
def patient_appointments_list(request):
    """Patient view: List all appointments."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointments = get_patient_appointments(request.user)
    return render(request, 'scheduling/patient/appointments.html', {'appointments': appointments})


@login_required
def patient_cancel_appointment(request, appointment_id):
    """Patient view: Cancel an appointment."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

    if request.method == 'POST':
        try:
            cancel_appointment(appointment)
            messages.success(request, 'Appointment cancelled successfully.')
        except ValueError as e:
            messages.error(request, str(e))

    return redirect('patient:patient_appointments')


# ========== DOCTOR VIEWS ==========

@login_required
def doctor_availability_view(request):
    """Doctor view: Manage availability windows."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    availability_windows = get_doctor_availability_windows(doctor_profile)

    return render(request, 'scheduling/doctor/availability.html', {
        'availability_windows': availability_windows
    })


@login_required
def doctor_schedule_view(request):
    """Doctor view: View upcoming appointments."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    appointments = get_upcoming_doctor_appointments(doctor_profile)

    return render(request, 'scheduling/doctor/schedule.html', {
        'appointments': appointments
    })


@login_required
def doctor_generate_slots(request):
    """Doctor view: Generate slots for the next 30 days."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    if request.method == 'POST':
        doctor_profile = request.user.doctor_profile
        days_ahead = int(request.POST.get('days_ahead', 30))

        created_slots = generate_slots_for_doctor(doctor_profile, days_ahead)
        messages.success(request, f'Generated {len(created_slots)} slots for the next {days_ahead} days.')

    return redirect('doctor:doctor_schedule')
