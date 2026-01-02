from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone

from apps.accounts.models import DoctorProfile
from apps.accounts.selectors import get_all_verified_doctors
from .models import Slot, Appointment, AvailabilityWindow
from .forms import AvailabilityWindowForm, ManualSlotForm, BlockSlotForm, get_appointment_type_formset
from .services import (
    book_appointment,
    cancel_appointment,
    generate_slots_for_doctor,
    create_availability_window,
    update_availability_window,
    delete_availability_window,
    create_manual_slot,
    block_slot,
    unblock_slot,
    delete_slot,
    log_slot_change
)
from .selectors import (
    get_available_slots_for_doctor,
    get_patient_appointments,
    get_doctor_appointments,
    get_doctor_availability_windows,
    get_upcoming_doctor_appointments,
    get_all_availability_windows,
    get_availability_summary,
    get_doctor_slots_for_calendar,
    get_slots_for_patient_view,
    has_slot_changes_since,
    get_enabled_appointment_types
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

    return redirect('doctor:doctor_availability')


# ========== DOCTOR AVAILABILITY MANAGEMENT (NEW) ==========

@login_required
def doctor_availability_manage(request):
    """Doctor view: Full availability management page with calendar."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    availability_windows = get_all_availability_windows(doctor_profile)
    summary = get_availability_summary(doctor_profile)

    # Get current week's slots for initial calendar render
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    slots = get_doctor_slots_for_calendar(doctor_profile, start_of_week, end_of_week)

    # Calculate prev/next week dates
    prev_week = start_of_week - timedelta(days=7)
    next_week = start_of_week + timedelta(days=7)

    # Generate list of dates for the current week
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    context = {
        'availability_windows': availability_windows,
        'summary': summary,
        'slots': slots,
        'today': today,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week.strftime('%Y-%m-%d'),
        'next_week': next_week.strftime('%Y-%m-%d'),
        'week_dates': week_dates,
        'window_form': AvailabilityWindowForm(),
        'manual_slot_form': ManualSlotForm(),
    }

    return render(request, 'scheduling/doctor/availability_manage.html', context)


@login_required
@require_POST
def doctor_create_availability_window(request):
    """HTMX: Create a new availability window."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    form = AvailabilityWindowForm(request.POST)
    if form.is_valid():
        try:
            data = form.cleaned_data
            window = create_availability_window(
                doctor_profile=request.user.doctor_profile,
                weekday=data['weekday'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                slot_duration_minutes=int(data['slot_duration_minutes']),
                buffer_before_minutes=int(data.get('buffer_before_minutes') or 0),
                buffer_after_minutes=int(data.get('buffer_after_minutes') or 0),
                appointment_type=data.get('appointment_type', 'video'),
                is_recurring=data.get('is_recurring', True),
                effective_date=data.get('effective_date'),
                end_date=data.get('end_date'),
            )
            messages.success(request, 'Availability window created successfully!')
            # Return updated windows list partial
            windows = get_all_availability_windows(request.user.doctor_profile)
            return render(request, 'scheduling/doctor/partials/_availability_windows_list.html', {
                'availability_windows': windows
            })
        except ValueError as e:
            return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)

    # Return form with errors
    return render(request, 'scheduling/doctor/partials/_window_form.html', {
        'form': form,
        'form_errors': form.errors
    }, status=400)


@login_required
@require_POST
def doctor_update_availability_window(request, window_id):
    """HTMX: Update an availability window."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    form = AvailabilityWindowForm(request.POST)
    if form.is_valid():
        try:
            data = form.cleaned_data
            window = update_availability_window(
                window_id=window_id,
                doctor_profile=request.user.doctor_profile,
                weekday=data['weekday'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                slot_duration_minutes=int(data['slot_duration_minutes']),
                buffer_before_minutes=int(data.get('buffer_before_minutes') or 0),
                buffer_after_minutes=int(data.get('buffer_after_minutes') or 0),
                appointment_type=data.get('appointment_type', 'video'),
                is_recurring=data.get('is_recurring', True),
                effective_date=data.get('effective_date'),
                end_date=data.get('end_date'),
            )
            messages.success(request, 'Availability window updated successfully!')
            windows = get_all_availability_windows(request.user.doctor_profile)
            return render(request, 'scheduling/doctor/partials/_availability_windows_list.html', {
                'availability_windows': windows
            })
        except ValueError as e:
            return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)

    return render(request, 'scheduling/doctor/partials/_window_form.html', {
        'form': form,
        'window_id': window_id
    }, status=400)


@login_required
@require_POST
def doctor_delete_availability_window(request, window_id):
    """HTMX: Delete an availability window."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    try:
        result = delete_availability_window(
            window_id=window_id,
            doctor_profile=request.user.doctor_profile
        )
        messages.success(request, f'Window deleted. {result["deleted_slots"]} future slots removed.')
        windows = get_all_availability_windows(request.user.doctor_profile)
        return render(request, 'scheduling/doctor/partials/_availability_windows_list.html', {
            'availability_windows': windows
        })
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_POST
def doctor_create_manual_slot(request):
    """HTMX: Create a manual/urgent slot."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    form = ManualSlotForm(request.POST)
    if form.is_valid():
        try:
            data = form.cleaned_data
            start_datetime = timezone.make_aware(
                datetime.combine(data['date'], data['start_time'])
            )
            end_datetime = timezone.make_aware(
                datetime.combine(data['date'], data['end_time'])
            )

            slot = create_manual_slot(
                doctor_profile=request.user.doctor_profile,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                appointment_type=data['appointment_type'],
                is_urgent=data.get('is_urgent', False),
                max_capacity=data.get('max_capacity', 1),
                notes=data.get('notes', '')
            )
            messages.success(request, 'Slot created successfully!')
            # Return updated calendar
            return doctor_calendar_slots(request)
        except ValueError as e:
            return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)

    return render(request, 'scheduling/doctor/partials/_manual_slot_form.html', {
        'form': form
    }, status=400)


@login_required
@require_POST
def doctor_block_slot(request, slot_id):
    """HTMX: Block a slot."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    reason = request.POST.get('reason', '')
    try:
        slot = block_slot(slot_id, request.user.doctor_profile, reason)
        messages.success(request, 'Slot blocked.')
        return doctor_calendar_slots(request)
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_POST
def doctor_unblock_slot(request, slot_id):
    """HTMX: Unblock a slot."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    try:
        slot = unblock_slot(slot_id, request.user.doctor_profile)
        messages.success(request, 'Slot unblocked.')
        return doctor_calendar_slots(request)
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_POST
def doctor_delete_slot(request, slot_id):
    """HTMX: Delete an unbooked slot."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    try:
        delete_slot(slot_id, request.user.doctor_profile)
        messages.success(request, 'Slot deleted.')
        return doctor_calendar_slots(request)
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_GET
def doctor_calendar_slots(request):
    """HTMX: Get calendar slots for a given week."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    # Get week from query params or default to current week
    week_start_param = request.GET.get('week_start')
    if week_start_param:
        start_of_week = datetime.strptime(week_start_param, '%Y-%m-%d').date()
    else:
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())

    end_of_week = start_of_week + timedelta(days=6)

    # Calculate prev/next week dates
    prev_week = start_of_week - timedelta(days=7)
    next_week = start_of_week + timedelta(days=7)

    # Generate list of dates for the week
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]

    slots = get_doctor_slots_for_calendar(
        request.user.doctor_profile,
        start_of_week,
        end_of_week
    )

    return render(request, 'scheduling/doctor/partials/_calendar_grid.html', {
        'slots': slots,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week.strftime('%Y-%m-%d'),
        'next_week': next_week.strftime('%Y-%m-%d'),
        'week_dates': week_dates,
        'today': timezone.now().date(),
    })


@login_required
def doctor_appointment_type_config(request):
    """Doctor view: Configure appointment types and pricing."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    formset = get_appointment_type_formset(doctor_profile, request.POST or None)

    if request.method == 'POST' and formset.is_valid():
        formset.save()
        messages.success(request, 'Appointment type settings updated!')
        return redirect('doctor:appointment_types')

    return render(request, 'scheduling/doctor/appointment_types.html', {
        'formset': formset
    })


# ========== PATIENT REAL-TIME UPDATES ==========

@login_required
@require_GET
def patient_slots_updates(request, doctor_id):
    """HTMX polling endpoint: Get updated slots for a doctor."""
    if request.user.role != 'patient':
        return HttpResponse(status=403)

    doctor = get_object_or_404(DoctorProfile, id=doctor_id, verification_status='verified')

    # Get last update timestamp from header
    last_update = request.headers.get('X-Last-Update')
    if last_update:
        try:
            last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            if not has_slot_changes_since(doctor, last_update_dt):
                return HttpResponse(status=204)  # No content - no updates
        except (ValueError, TypeError):
            pass

    # Return updated slots view
    slots_by_date = get_slots_for_patient_view(doctor)
    appointment_types = get_enabled_appointment_types(doctor)

    response = render(request, 'scheduling/patient/partials/_available_slots.html', {
        'doctor': doctor,
        'slots_by_date': slots_by_date,
        'appointment_types': appointment_types,
    })
    response['X-Last-Update'] = timezone.now().isoformat()
    return response
