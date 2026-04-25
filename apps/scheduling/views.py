from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django_ratelimit.decorators import ratelimit

from apps.accounts.models import DoctorProfile
from apps.accounts.selectors import get_filtered_doctors, get_all_specializations, get_all_languages
from .models import Slot, Appointment, AvailabilityWindow, BodyPart, Condition, SymptomCategory, Symptom, HealthRecord, WaitlistEntry, Referral
from .forms import AvailabilityWindowForm, ManualSlotForm, BlockSlotForm, get_appointment_type_formset
from .services import (
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
    generate_slots_for_doctor,
    create_availability_window,
    update_availability_window,
    delete_availability_window,
    create_manual_slot,
    block_slot,
    unblock_slot,
    delete_slot,
    create_review,
    create_prescription,
    create_time_off_block,
    delete_time_off_block,
    join_waitlist,
    leave_waitlist,
    create_health_record,
    share_health_record_with_doctor,
    get_patient_health_records,
    get_shared_records_for_doctor,
    create_referral,
    create_availability_exception,
    delete_availability_exception,
    respond_to_review,
    generate_billing_pdf,
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
    get_enabled_appointment_types,
    get_doctor_reviews,
    get_patient_reviewable_appointments,
    can_patient_review_appointment,
    get_doctor_analytics,
    get_prescription_for_appointment,
    get_doctor_time_off_blocks,
    get_patient_history_for_doctor,
    get_availability_exceptions,
)


# ========== PATIENT VIEWS ==========

@login_required
def patient_doctors_list(request):
    """Patient view: List all verified doctors with filtering and search."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    # Get filter parameters from request
    search = request.GET.get('search', '').strip()
    specialization = request.GET.get('specialization', '').strip()
    min_rating = request.GET.get('min_rating')
    min_experience = request.GET.get('min_experience')
    max_price = request.GET.get('max_price')
    has_availability = request.GET.get('has_availability') == 'on'
    sort_by = request.GET.get('sort_by', 'rating')
    language = request.GET.get('language', '').strip()
    available_today = request.GET.get('available_today') == 'on'
    second_opinion = request.GET.get('second_opinion') == 'on'
    group_sessions_only = request.GET.get('group_sessions_only') == 'on'

    # Convert numeric filters
    try:
        min_rating = int(min_rating) if min_rating else None
    except ValueError:
        min_rating = None

    try:
        min_experience = int(min_experience) if min_experience else None
    except ValueError:
        min_experience = None

    try:
        max_price = float(max_price) if max_price else None
    except ValueError:
        max_price = None

    # Get filtered doctors
    doctors = get_filtered_doctors(
        search=search if search else None,
        specialization=specialization if specialization else None,
        min_rating=min_rating,
        min_experience=min_experience,
        max_price=max_price,
        has_availability=has_availability,
        sort_by=sort_by,
        language=language if language else None,
        available_today=available_today,
        offers_second_opinions=True if second_opinion else None,
        group_sessions_only=group_sessions_only,
    )

    # Get all specializations and languages for filter dropdowns
    specializations = get_all_specializations()
    languages = get_all_languages()

    context = {
        'doctors': doctors,
        'specializations': specializations,
        'languages': languages,
        # Pass current filter values back to template
        'current_filters': {
            'search': search,
            'specialization': specialization,
            'min_rating': min_rating,
            'min_experience': min_experience,
            'max_price': max_price,
            'has_availability': has_availability,
            'sort_by': sort_by,
            'language': language,
            'available_today': available_today,
            'second_opinion': second_opinion,
            'group_sessions_only': group_sessions_only,
        }
    }

    # For HTMX requests, return just the doctors grid
    if request.headers.get('HX-Request'):
        return render(request, 'scheduling/patient/partials/_doctors_grid.html', context)

    return render(request, 'scheduling/patient/doctors_list.html', context)


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
@ratelimit(key='user', rate='10/h', method='POST', block=True)
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


@login_required
def patient_reschedule_appointment(request, appointment_id):
    """Patient view: Reschedule an appointment to a different slot."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

    if appointment.status != 'scheduled' or appointment.start_datetime <= timezone.now():
        messages.error(request, 'This appointment cannot be rescheduled.')
        return redirect('patient:patient_appointments')

    available_slots = get_available_slots_for_doctor(appointment.doctor)
    # Exclude the currently booked slot
    available_slots = [s for s in available_slots if s.id != appointment.slot.id]

    if request.method == 'POST':
        slot_id = request.POST.get('slot_id')
        new_slot = get_object_or_404(Slot, id=slot_id)
        try:
            reschedule_appointment(appointment, new_slot)
            messages.success(request, 'Appointment rescheduled successfully.')
            return redirect('patient:patient_appointments')
        except ValueError as e:
            messages.error(request, str(e))

    return render(request, 'scheduling/patient/reschedule.html', {
        'appointment': appointment,
        'available_slots': available_slots,
    })


# ========== DOCTOR VIEWS ==========

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
    """HTMX: Create a new availability window with multi-type support."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    form = AvailabilityWindowForm(request.POST)
    if form.is_valid():
        try:
            data = form.cleaned_data

            # Get the first enabled type as the default appointment_type for legacy support
            type_configs = form.get_type_configs()
            enabled_types = [tc for tc in type_configs if tc[1]]  # (type, is_enabled, price)
            default_type = enabled_types[0][0] if enabled_types else 'video'

            window = create_availability_window(
                doctor_profile=request.user.doctor_profile,
                weekday=data['weekday'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                slot_duration_minutes=int(data['slot_duration_minutes']),
                buffer_before_minutes=int(data.get('buffer_before_minutes') or 0),
                buffer_after_minutes=int(data.get('buffer_after_minutes') or 0),
                appointment_type=default_type,
                is_recurring=data.get('is_recurring', True),
                effective_date=data.get('effective_date'),
                end_date=data.get('end_date'),
                type_configs=type_configs,
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

            # Get type configs from form
            type_configs = form.get_type_configs()
            enabled_types = [tc for tc in type_configs if tc[1]]
            default_type = enabled_types[0][0] if enabled_types else 'video'

            window = update_availability_window(
                window_id=window_id,
                doctor_profile=request.user.doctor_profile,
                type_configs=type_configs,
                regenerate_slots=True,
                weekday=data['weekday'],
                start_time=data['start_time'],
                end_time=data['end_time'],
                slot_duration_minutes=int(data['slot_duration_minutes']),
                buffer_before_minutes=int(data.get('buffer_before_minutes') or 0),
                buffer_after_minutes=int(data.get('buffer_after_minutes') or 0),
                appointment_type=default_type,
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
def doctor_get_availability_window(request, window_id):
    """HTMX: Get availability window form for editing."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    try:
        window = AvailabilityWindow.objects.get(
            id=window_id,
            doctor=request.user.doctor_profile
        )
    except AvailabilityWindow.DoesNotExist:
        return HttpResponse('Window not found', status=404)

    form = AvailabilityWindowForm(instance=window)

    return render(request, 'scheduling/doctor/partials/_window_edit_form.html', {
        'form': form,
        'window': window
    })


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


def _render_doctor_calendar(request):
    """Render the calendar grid partial for the doctor's current week."""
    week_start_param = request.GET.get('week_start')
    if week_start_param:
        start_of_week = datetime.strptime(week_start_param, '%Y-%m-%d').date()
    else:
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())

    end_of_week = start_of_week + timedelta(days=6)
    prev_week = start_of_week - timedelta(days=7)
    next_week = start_of_week + timedelta(days=7)
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    slots = get_doctor_slots_for_calendar(request.user.doctor_profile, start_of_week, end_of_week)

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

            create_manual_slot(
                doctor_profile=request.user.doctor_profile,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                appointment_type=data['appointment_type'],
                is_urgent=data.get('is_urgent', False),
                max_capacity=data.get('max_capacity', 1),
                notes=data.get('notes', '')
            )
            messages.success(request, 'Slot created successfully!')
            return _render_doctor_calendar(request)
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
        block_slot(slot_id, request.user.doctor_profile, reason)
        messages.success(request, 'Slot blocked.')
        return _render_doctor_calendar(request)
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_POST
def doctor_unblock_slot(request, slot_id):
    """HTMX: Unblock a slot."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)

    try:
        unblock_slot(slot_id, request.user.doctor_profile)
        messages.success(request, 'Slot unblocked.')
        return _render_doctor_calendar(request)
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
        return _render_doctor_calendar(request)
    except ValueError as e:
        return HttpResponse(f'<div class="text-red-600 p-2">{str(e)}</div>', status=400)


@login_required
@require_GET
def doctor_calendar_slots(request):
    """HTMX: Get calendar slots for a given week."""
    if request.user.role != 'doctor':
        return HttpResponse(status=403)
    return _render_doctor_calendar(request)


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


@login_required
def doctor_analytics_view(request):
    """Doctor view: Personal analytics dashboard."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    analytics = get_doctor_analytics(request.user.doctor_profile)
    reviews = get_doctor_reviews(request.user.doctor_profile)
    return render(request, 'scheduling/doctor/analytics.html', {'analytics': analytics, 'reviews': reviews})


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


# ========== SYMPTOM SELECTOR VIEWS ==========

@login_required
@require_GET
def get_body_parts(request):
    """HTMX: Get all body parts grouped by category."""
    if request.user.role != 'patient':
        return HttpResponse(status=403)

    body_parts = BodyPart.objects.filter(is_active=True).prefetch_related('conditions')

    # Group by category
    categories = {}
    for bp in body_parts:
        cat_display = bp.get_category_display()
        if cat_display not in categories:
            categories[cat_display] = []
        categories[cat_display].append(bp)

    return render(request, 'scheduling/patient/partials/_body_parts.html', {
        'categories': categories
    })


@login_required
@require_GET
def get_conditions(request, body_part_id):
    """HTMX: Get conditions for a specific body part."""
    if request.user.role != 'patient':
        return HttpResponse(status=403)

    body_part = get_object_or_404(BodyPart, id=body_part_id, is_active=True)
    conditions = body_part.conditions.filter(is_active=True)

    return render(request, 'scheduling/patient/partials/_conditions.html', {
        'body_part': body_part,
        'conditions': conditions
    })


@login_required
@require_GET
def get_symptoms(request):
    """HTMX: Get all symptoms grouped by category."""
    if request.user.role != 'patient':
        return HttpResponse(status=403)

    categories = SymptomCategory.objects.filter(is_active=True).prefetch_related('symptoms')

    return render(request, 'scheduling/patient/partials/_symptoms.html', {
        'categories': categories
    })


# ========== REVIEW VIEWS ==========

@login_required
def patient_reviews_list(request):
    """Patient view: List appointments that can be reviewed."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    reviewable = get_patient_reviewable_appointments(request.user)

    return render(request, 'scheduling/patient/reviews.html', {
        'reviewable_appointments': reviewable
    })


@login_required
def patient_submit_review(request, appointment_id):
    """Patient view: Submit a review for a completed appointment."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

    if not can_patient_review_appointment(request.user, appointment):
        messages.error(request, 'You cannot review this appointment.')
        return redirect('patient:patient_appointments')

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '').strip()

        if not rating:
            messages.error(request, 'Please select a rating.')
            return render(request, 'scheduling/patient/submit_review.html', {
                'appointment': appointment
            })

        try:
            rating = int(rating)
            review = create_review(appointment, request.user, rating, comment)
            messages.success(request, 'Thank you for your review!')
            return redirect('patient:patient_appointments')
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'scheduling/patient/submit_review.html', {
                'appointment': appointment
            })

    return render(request, 'scheduling/patient/submit_review.html', {
        'appointment': appointment
    })


@login_required
@require_GET
def doctor_reviews_partial(request, doctor_id):
    """HTMX: Get reviews list for a doctor."""
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    reviews = get_doctor_reviews(doctor)

    return render(request, 'scheduling/patient/partials/_reviews_list.html', {
        'doctor': doctor,
        'reviews': reviews
    })


# ========== PRESCRIPTION VIEWS ==========

@login_required
def doctor_write_prescription(request, appointment_id):
    """Doctor view: Write a prescription for a completed appointment."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    appointment = get_object_or_404(
        Appointment, id=appointment_id, doctor=request.user.doctor_profile
    )

    if appointment.status != 'completed':
        messages.error(request, 'Prescriptions can only be written for completed appointments.')
        return redirect('doctor:doctor_schedule')

    existing = get_prescription_for_appointment(appointment)
    if existing:
        messages.info(request, 'A prescription already exists for this appointment.')
        return redirect('doctor:doctor_schedule')

    if request.method == 'POST':
        diagnosis = request.POST.get('diagnosis', '').strip()
        medications = request.POST.get('medications', '').strip()
        instructions = request.POST.get('instructions', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not medications:
            messages.error(request, 'Please enter at least one medication.')
        else:
            try:
                create_prescription(appointment, diagnosis, medications, instructions, notes)
                messages.success(request, 'Prescription written successfully.')
                return redirect('doctor:doctor_schedule')
            except ValueError as e:
                messages.error(request, str(e))

    return render(request, 'scheduling/doctor/write_prescription.html', {
        'appointment': appointment
    })


@login_required
def patient_download_prescription(request, appointment_id):
    """Patient view: Download prescription as PDF."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)
    prescription = get_prescription_for_appointment(appointment)

    if not prescription:
        messages.error(request, 'No prescription found for this appointment.')
        return redirect('patient:patient_appointments')

    from io import BytesIO
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=inch, rightMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Heading1'], fontSize=20, spaceAfter=4)
    heading_style = ParagraphStyle('heading', parent=styles['Heading2'], fontSize=12, spaceAfter=4, textColor=colors.HexColor('#1d4ed8'))
    normal_style = ParagraphStyle('normal', parent=styles['Normal'], fontSize=10, spaceAfter=6, leading=14)
    small_style = ParagraphStyle('small', parent=styles['Normal'], fontSize=9, textColor=colors.gray)

    story = []

    # Header
    story.append(Paragraph("MedConsult", title_style))
    story.append(Paragraph("Digital Prescription", styles['Heading2']))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1d4ed8')))
    story.append(Spacer(1, 0.2 * inch))

    # Patient & Doctor info
    info_data = [
        ['Patient:', prescription.patient.get_display_name(), 'Doctor:', f"Dr. {prescription.doctor.user.get_display_name()}"],
        ['Date:', prescription.created_at.strftime('%B %d, %Y'), 'Specialization:', prescription.doctor.specialization],
    ]
    info_table = Table(info_data, colWidths=[1.2*inch, 2.5*inch, 1.2*inch, 2.5*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.15 * inch))

    if prescription.diagnosis:
        story.append(Paragraph("Diagnosis", heading_style))
        story.append(Paragraph(prescription.diagnosis, normal_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("Medications", heading_style))
    story.append(Paragraph(prescription.medications.replace('\n', '<br/>'), normal_style))
    story.append(Spacer(1, 0.1 * inch))

    if prescription.instructions:
        story.append(Paragraph("Instructions", heading_style))
        story.append(Paragraph(prescription.instructions.replace('\n', '<br/>'), normal_style))
        story.append(Spacer(1, 0.1 * inch))

    if prescription.notes:
        story.append(Paragraph("Notes", heading_style))
        story.append(Paragraph(prescription.notes.replace('\n', '<br/>'), normal_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Spacer(1, 0.3 * inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(f"Generated by MedConsult on {prescription.created_at.strftime('%B %d, %Y')}", small_style))

    doc.build(story)
    buffer.seek(0)

    filename = f"prescription_{appointment_id}_{prescription.created_at.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ========== FEATURE 3: DOCTOR TIME-OFF VIEWS ==========

@login_required
def doctor_time_off_list(request):
    """Doctor view: Manage time-off blocks."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    blocks = get_doctor_time_off_blocks(doctor_profile)

    if request.method == 'POST':
        start_date_str = request.POST.get('start_date', '').strip()
        end_date_str = request.POST.get('end_date', '').strip()
        reason = request.POST.get('reason', '').strip()

        if not start_date_str or not end_date_str:
            messages.error(request, 'Please provide both start and end dates.')
        else:
            try:
                from datetime import date as date_type
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_date < start_date:
                    messages.error(request, 'End date must be on or after start date.')
                else:
                    create_time_off_block(doctor_profile, start_date, end_date, reason)
                    messages.success(request, 'Time off block created. All slots in this range have been blocked.')
                    return redirect('doctor:time_off_list')
            except ValueError as e:
                messages.error(request, f'Error: {str(e)}')

    return render(request, 'scheduling/doctor/time_off.html', {
        'blocks': blocks,
    })


@login_required
@require_POST
def doctor_delete_time_off(request, block_id):
    """Doctor view: Delete a time-off block."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    try:
        delete_time_off_block(block_id, request.user.doctor_profile)
        messages.success(request, 'Time off block deleted. Affected slots have been unblocked.')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')

    return redirect('doctor:time_off_list')


# ========== FEATURE 4: WAITLIST VIEWS ==========

@login_required
@require_POST
def patient_join_waitlist(request, doctor_id):
    """Patient view: Join a doctor's waitlist."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id, verification_status='verified')
    appointment_type = request.POST.get('appointment_type', '')
    notes = request.POST.get('notes', '').strip()

    entry, created = join_waitlist(doctor, request.user, appointment_type=appointment_type, notes=notes)
    if created:
        messages.success(request, f"You've been added to Dr. {doctor.user.get_display_name()}'s waitlist.")
    else:
        messages.info(request, "You're already on this doctor's waitlist.")

    return redirect('patient:doctor_detail', doctor_id=doctor_id)


@login_required
@require_POST
def patient_leave_waitlist(request, doctor_id):
    """Patient view: Leave a doctor's waitlist."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    leave_waitlist(doctor, request.user)
    messages.success(request, f"You've been removed from Dr. {doctor.user.get_display_name()}'s waitlist.")

    return redirect('patient:doctor_detail', doctor_id=doctor_id)


# ========== FEATURE 5: HEALTH RECORDS VIEWS ==========

@login_required
def patient_health_records(request):
    """Patient view: List and upload health records."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    records = get_patient_health_records(request.user)

    if request.method == 'POST':
        record_type = request.POST.get('record_type', '').strip()
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        date_of_record_str = request.POST.get('date_of_record', '').strip()
        file = request.FILES.get('file')

        if not record_type or not title:
            messages.error(request, 'Please provide a record type and title.')
        else:
            date_of_record = None
            if date_of_record_str:
                try:
                    date_of_record = datetime.strptime(date_of_record_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            create_health_record(
                request.user, record_type, title,
                description=description, file=file, date_of_record=date_of_record
            )
            messages.success(request, 'Health record uploaded successfully.')
            return redirect('patient:patient_health_records')

    # Doctors this patient has had appointments with (for share dropdown)
    from apps.accounts.models import DoctorProfile
    my_doctors = DoctorProfile.objects.filter(
        doctor_appointments__patient=request.user
    ).select_related('user').distinct()

    return render(request, 'scheduling/patient/health_records.html', {
        'records': records,
        'record_types': HealthRecord.RECORD_TYPES,
        'my_doctors': my_doctors,
    })


@login_required
@require_POST
def patient_delete_health_record(request, record_id):
    """Patient view: Delete a health record."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    record = get_object_or_404(HealthRecord, id=record_id, patient=request.user)
    record.delete()
    messages.success(request, 'Health record deleted.')
    return redirect('patient:patient_health_records')


@login_required
@require_POST
def patient_share_health_record(request, record_id):
    """Patient view: Share a health record with a doctor."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    record = get_object_or_404(HealthRecord, id=record_id, patient=request.user)
    doctor_id = request.POST.get('doctor_id')
    doctor = get_object_or_404(DoctorProfile, id=doctor_id, verification_status='verified')

    share_health_record_with_doctor(record, doctor)

    from apps.adminpanel.models import HealthRecordAccessLog
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    HealthRecordAccessLog.objects.create(
        record=record,
        accessed_by=request.user,
        access_type='shared',
        ip_address=ip,
    )

    messages.success(request, f'Record shared with Dr. {doctor.user.get_display_name()}.')
    return redirect('patient:patient_health_records')


@login_required
def doctor_view_shared_records(request, patient_id):
    """Doctor view: See health records shared with them by a patient."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    from apps.accounts.models import User as UserModel
    from apps.adminpanel.models import HealthRecordAccessLog
    patient = get_object_or_404(UserModel, id=patient_id, role='patient')
    doctor_profile = request.user.doctor_profile
    records = get_shared_records_for_doctor(doctor_profile, patient)

    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    for record in records:
        HealthRecordAccessLog.objects.create(
            record=record,
            accessed_by=request.user,
            access_type='viewed',
            ip_address=ip,
        )

    return render(request, 'scheduling/doctor/patient_records.html', {
        'patient': patient,
        'records': records,
    })


# ========== FEATURE 6: FOLLOW-UP APPOINTMENT VIEWS ==========

@login_required
def doctor_schedule_followup(request, appointment_id):
    """Doctor view: Suggest a follow-up slot to a patient."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    appointment = get_object_or_404(
        Appointment, id=appointment_id, doctor=request.user.doctor_profile
    )

    # Get future available slots for this doctor (next 14 days)
    future_slots = Slot.objects.filter(
        doctor=request.user.doctor_profile,
        is_booked=False,
        is_blocked=False,
        start_datetime__gt=timezone.now(),
        start_datetime__date__lte=(timezone.now().date() + timedelta(days=14))
    ).order_by('start_datetime')

    if request.method == 'POST':
        slot_id = request.POST.get('slot_id')
        reason = request.POST.get('reason', '').strip()
        slot = get_object_or_404(Slot, id=slot_id, doctor=request.user.doctor_profile)

        from apps.accounts.services import create_notification
        create_notification(
            appointment.patient, 'appointment_rescheduled',
            f"Dr. {request.user.get_display_name()} recommends a follow-up",
            reason or f"Dr. {request.user.get_display_name()} has suggested a follow-up appointment.",
            link=f"/patient/book/{slot.id}/"
        )
        messages.success(request, f'Follow-up suggestion sent to {appointment.patient.get_display_name()}.')
        return redirect('doctor:doctor_schedule')

    return render(request, 'scheduling/doctor/schedule_followup.html', {
        'appointment': appointment,
        'future_slots': future_slots,
    })


# ========== FEATURE 7: MEDICAL HISTORY VIEWS ==========

@login_required
def doctor_patient_history(request, patient_id):
    """Doctor view: View full history of a patient with this doctor."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    from apps.accounts.models import User as UserModel
    patient = get_object_or_404(UserModel, id=patient_id, role='patient')
    doctor_profile = request.user.doctor_profile
    history = get_patient_history_for_doctor(patient, doctor_profile)

    return render(request, 'scheduling/doctor/patient_history.html', {
        'patient': patient,
        'history': history,
    })


# ========== FEATURE 9: REFERRAL VIEWS ==========

@login_required
def doctor_create_referral(request, appointment_id):
    """Doctor view: Create a referral for a patient."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    appointment = get_object_or_404(
        Appointment, id=appointment_id, doctor=request.user.doctor_profile
    )

    all_doctors = DoctorProfile.objects.filter(
        verification_status='verified'
    ).exclude(id=request.user.doctor_profile.id).select_related('user').order_by('user__first_name')

    if request.method == 'POST':
        referred_to_id = request.POST.get('referred_to_doctor_id')
        reason = request.POST.get('reason', '').strip()
        notes = request.POST.get('notes', '').strip()

        if not referred_to_id or not reason:
            messages.error(request, 'Please select a doctor and provide a reason.')
        else:
            referred_to = get_object_or_404(DoctorProfile, id=referred_to_id, verification_status='verified')
            create_referral(
                referring_doctor=request.user.doctor_profile,
                referred_to_doctor=referred_to,
                patient=appointment.patient,
                reason=reason,
                notes=notes,
            )
            messages.success(request, f'Referral sent to Dr. {referred_to.user.get_display_name()} for {appointment.patient.get_display_name()}.')
            return redirect('doctor:doctor_schedule')

    return render(request, 'scheduling/doctor/create_referral.html', {
        'appointment': appointment,
        'all_doctors': all_doctors,
    })


@login_required
def patient_referrals_list(request):
    """Patient view: List all referrals."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    referrals = Referral.objects.filter(patient=request.user).select_related(
        'referring_doctor__user', 'referred_to_doctor__user'
    ).order_by('-created_at')

    return render(request, 'scheduling/patient/referrals.html', {
        'referrals': referrals,
    })


# ============ BILLING DOWNLOAD ============

@login_required
def patient_billing_download(request, appointment_id):
    """Download billing summary PDF for an appointment."""
    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

    if appointment.status != 'completed':
        messages.error(request, 'Billing summary is only available for completed appointments.')
        return redirect('patient:patient_appointments')

    pdf_buffer = generate_billing_pdf(appointment)

    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="billing_{appointment_id}.pdf"'
    return response


# ============ AVAILABILITY EXCEPTIONS ============

@login_required
def doctor_exception_list(request):
    """Doctor view: List availability exceptions."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    exceptions = get_availability_exceptions(doctor_profile)

    return render(request, 'scheduling/doctor/time_off.html', {
        'time_off_blocks': get_doctor_time_off_blocks(doctor_profile),
        'exceptions': exceptions,
    })


@login_required
@require_POST
def doctor_exception_create(request):
    """Doctor view: Create a one-off availability exception."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    date_str = request.POST.get('date', '')
    start_time_str = request.POST.get('start_time', '')
    end_time_str = request.POST.get('end_time', '')
    reason = request.POST.get('reason', '')

    try:
        from datetime import date as date_type, time as time_type
        exc_date = date_type.fromisoformat(date_str)
        start_time = None
        end_time = None
        if start_time_str:
            start_time = time_type.fromisoformat(start_time_str)
        if end_time_str:
            end_time = time_type.fromisoformat(end_time_str)
        create_availability_exception(doctor_profile, exc_date, start_time, end_time, reason)
        messages.success(request, f'Exception added for {exc_date}.')
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('doctor:time_off_list')


@login_required
@require_POST
def doctor_exception_delete(request, exception_id):
    """Doctor view: Delete an availability exception."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    doctor_profile = request.user.doctor_profile
    try:
        delete_availability_exception(exception_id, doctor_profile)
        messages.success(request, 'Exception removed.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('doctor:time_off_list')


# ============ REVIEW RESPONSES ============

@login_required
@require_POST
def doctor_respond_to_review(request, review_id):
    """Doctor view: Respond to a patient review."""
    if request.user.role != 'doctor':
        return HttpResponseForbidden("Access denied. Doctors only.")

    from .models import Review
    review = get_object_or_404(Review, id=review_id)
    doctor_profile = request.user.doctor_profile
    response_text = request.POST.get('response_text', '').strip()

    try:
        respond_to_review(review, doctor_profile, response_text)
        messages.success(request, 'Your response has been posted.')
    except ValueError as e:
        messages.error(request, str(e))

    # Redirect back to analytics (where reviews are shown)
    return redirect('doctor:doctor_analytics')


# ============ PATIENT DATA EXPORT ============

@login_required
def patient_data_export(request):
    """Patient view: Export all personal data as JSON (GDPR/HIPAA compliance)."""
    import json
    from django.http import HttpResponse

    if request.user.role != 'patient':
        return HttpResponseForbidden("Access denied. Patients only.")

    user = request.user
    profile = getattr(user, 'patient_profile', None)

    appointments_qs = Appointment.objects.filter(patient=user).select_related(
        'slot__doctor__user'
    ).order_by('-created_at')

    health_records_qs = HealthRecord.objects.filter(patient=user).order_by('-created_at')

    prescriptions_qs = []
    for appt in appointments_qs:
        if hasattr(appt, 'prescription'):
            prescriptions_qs.append(appt.prescription)

    from apps.adminpanel.models import HealthRecordAccessLog
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    for record in health_records_qs:
        HealthRecordAccessLog.objects.create(
            record=record,
            accessed_by=user,
            access_type='downloaded',
            ip_address=ip,
        )

    data = {
        'export_date': timezone.now().isoformat(),
        'profile': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined.isoformat(),
            'date_of_birth': str(profile.date_of_birth) if profile and profile.date_of_birth else None,
            'gender': profile.gender if profile else None,
            'phone_number': profile.phone_number if profile else None,
            'address': profile.address if profile else None,
        },
        'appointments': [
            {
                'id': a.id,
                'doctor': a.slot.doctor.user.get_display_name() if a.slot and a.slot.doctor else None,
                'appointment_type': a.appointment_type,
                'status': a.status,
                'start': a.slot.start_datetime.isoformat() if a.slot else None,
                'reason': a.reason,
                'created_at': a.created_at.isoformat(),
            }
            for a in appointments_qs
        ],
        'health_records': [
            {
                'id': r.id,
                'title': r.title,
                'record_type': r.record_type,
                'description': r.description,
                'date_of_record': str(r.date_of_record) if r.date_of_record else None,
                'created_at': r.created_at.isoformat(),
            }
            for r in health_records_qs
        ],
        'prescriptions': [
            {
                'id': p.id,
                'appointment_id': p.appointment_id,
                'diagnosis': p.diagnosis,
                'medications': p.medications,
                'instructions': p.instructions,
                'created_at': p.created_at.isoformat(),
            }
            for p in prescriptions_qs
        ],
    }

    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json',
    )
    response['Content-Disposition'] = f'attachment; filename="medconsult_export_{user.id}.json"'
    return response
