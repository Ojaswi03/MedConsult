"""
Views for adminpanel app - comprehensive admin dashboard.
"""
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.utils import timezone

from apps.accounts.models import DoctorProfile, User
from apps.scheduling.models import Appointment, Slot

from . import selectors
from . import services


def admin_required(view_func):
    """Decorator to restrict access to platform staff only."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        from apps.accounts.permissions import is_platform_staff
        if not is_platform_staff(request.user):
            return HttpResponseForbidden("Access denied. Admins only.")
        return view_func(request, *args, **kwargs)
    return wrapper


# ============ DASHBOARD ============

@admin_required
def dashboard(request):
    """Main admin dashboard with analytics."""
    overview = selectors.get_dashboard_overview()
    activity = selectors.get_activity_feed(limit=10)

    return render(request, 'adminpanel/dashboard.html', {
        'overview': overview,
        'pending_doctors': activity['pending_doctors'],
        'recent_appointments': activity['appointments'],
        'recent_admin_actions': activity['admin_actions'],
    })


@admin_required
@require_GET
def dashboard_charts_data(request):
    """API endpoint for dashboard chart data."""
    user_growth = selectors.get_user_growth_data(days=30)
    appointment_stats = selectors.get_appointment_stats_by_status()
    type_stats = selectors.get_appointment_stats_by_type()

    return JsonResponse({
        'user_growth': list(user_growth),
        'appointment_stats': list(appointment_stats),
        'type_stats': list(type_stats),
    })


# ============ USER MANAGEMENT ============

@admin_required
def users_list(request):
    """Enhanced users list with filtering."""
    role = request.GET.get('role', '')
    is_active = request.GET.get('is_active', '')
    search = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))

    is_active_filter = None
    if is_active == 'true':
        is_active_filter = True
    elif is_active == 'false':
        is_active_filter = False

    result = selectors.get_users_filtered(
        role=role or None,
        is_active=is_active_filter,
        search_query=search or None,
        limit=25,
        offset=(page - 1) * 25
    )

    # For HTMX requests, return just the table
    if request.headers.get('HX-Request'):
        return render(request, 'adminpanel/partials/_users_table.html', {
            'users': result['users'],
            'total': result['total'],
            'has_more': result['has_more'],
            'current_page': page,
        })

    return render(request, 'adminpanel/users_list.html', {
        'users': result['users'],
        'total': result['total'],
        'has_more': result['has_more'],
        'current_page': page,
        'filters': {
            'role': role,
            'is_active': is_active,
            'search': search,
        }
    })


@admin_required
def user_detail(request, user_id):
    """Detailed user view."""
    result = selectors.get_user_detail(user_id)
    ip_address = services.get_client_ip(request)

    # Log this view
    services.log_user_view(request.user, result['user'], ip_address)

    # For HTMX requests, return modal content
    if request.headers.get('HX-Request'):
        return render(request, 'adminpanel/partials/_user_detail_modal.html', result)

    return render(request, 'adminpanel/user_detail.html', result)


@admin_required
@require_POST
def user_toggle_active(request, user_id):
    """Toggle user active status."""
    ip_address = services.get_client_ip(request)
    user = get_object_or_404(User, id=user_id)

    # Toggle the status
    new_status = not user.is_active
    services.toggle_user_active(user_id, request.user, new_status, ip_address)

    action = "activated" if new_status else "deactivated"
    messages.success(request, f'User {user.email} has been {action}.')

    if request.headers.get('HX-Request'):
        # Return updated user row
        return render(request, 'adminpanel/partials/_user_row.html', {'user': user})

    return redirect('adminpanel:users_list')


@admin_required
def users_export(request):
    """Export users to CSV."""
    role = request.GET.get('role', '')
    is_active = request.GET.get('is_active', '')

    is_active_filter = None
    if is_active == 'true':
        is_active_filter = True
    elif is_active == 'false':
        is_active_filter = False

    result = selectors.get_users_filtered(
        role=role or None,
        is_active=is_active_filter,
        limit=10000
    )

    csv_content = services.export_users_csv(result['users'])
    ip_address = services.get_client_ip(request)
    services.log_export(request.user, 'users', result['total'], ip_address)

    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    return response


# ============ DOCTOR MANAGEMENT ============

@admin_required
def doctors_list(request):
    """All doctors with statistics."""
    doctors = selectors.get_all_doctors_with_stats()
    status_filter = request.GET.get('status', '')

    if status_filter:
        doctors = doctors.filter(verification_status=status_filter)

    return render(request, 'adminpanel/doctors_list.html', {
        'doctors': doctors,
        'status_filter': status_filter,
    })


@admin_required
def doctor_detail(request, doctor_id):
    """Detailed doctor statistics."""
    stats = selectors.get_doctor_statistics(doctor_id)
    ip_address = services.get_client_ip(request)

    # Log this view
    services.log_user_view(request.user, stats['doctor'].user, ip_address)

    if request.headers.get('HX-Request'):
        return render(request, 'adminpanel/partials/_doctor_detail_modal.html', stats)

    return render(request, 'adminpanel/doctor_detail.html', stats)


@admin_required
def doctor_document_view(request, doctor_id, doc_type):
    """View doctor's uploaded documents."""
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    ip_address = services.get_client_ip(request)

    # Log document view
    services.log_document_view(request.user, doctor, doc_type, ip_address)

    # Get the document URL based on type
    doc_url = None
    if doc_type == 'license' and doctor.medical_license_document:
        doc_url = doctor.medical_license_document.url
    elif doc_type == 'government_id' and doctor.government_id_document:
        doc_url = doctor.government_id_document.url

    return render(request, 'adminpanel/partials/_document_viewer.html', {
        'doctor': doctor,
        'doc_type': doc_type,
        'doc_url': doc_url,
    })


@admin_required
def doctor_verification_queue(request):
    """Enhanced doctor verification queue."""
    pending_doctors = selectors.get_pending_doctors_detailed()

    return render(request, 'adminpanel/doctor_verification.html', {
        'pending_doctors': pending_doctors
    })


@admin_required
@require_POST
def verify_doctor(request, doctor_id):
    """Approve a doctor with logging."""
    ip_address = services.get_client_ip(request)
    doctor = services.verify_doctor_with_logging(doctor_id, request.user, ip_address)

    messages.success(request, f'Dr. {doctor.user.get_display_name()} has been verified.')

    if request.headers.get('HX-Request'):
        # Return updated verification queue
        pending_doctors = selectors.get_pending_doctors_detailed()
        return render(request, 'adminpanel/partials/_verification_queue.html', {
            'pending_doctors': pending_doctors
        })

    return redirect('adminpanel:verification_queue')


@admin_required
@require_POST
def reject_doctor(request, doctor_id):
    """Reject a doctor with reason and logging."""
    reason = request.POST.get('reason', '')
    ip_address = services.get_client_ip(request)
    doctor = services.reject_doctor_with_logging(doctor_id, request.user, reason, ip_address)

    messages.warning(request, f'Dr. {doctor.user.get_display_name()} has been rejected.')

    if request.headers.get('HX-Request'):
        pending_doctors = selectors.get_pending_doctors_detailed()
        return render(request, 'adminpanel/partials/_verification_queue.html', {
            'pending_doctors': pending_doctors
        })

    return redirect('adminpanel:verification_queue')


# ============ APPOINTMENT MANAGEMENT ============

@admin_required
def appointments_list(request):
    """Enhanced appointments list with filtering."""
    status = request.GET.get('status', '')
    appointment_type = request.GET.get('type', '')
    search = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))

    result = selectors.get_appointments_filtered(
        status=status or None,
        appointment_type=appointment_type or None,
        search_query=search or None,
        limit=25,
        offset=(page - 1) * 25
    )

    if request.headers.get('HX-Request'):
        return render(request, 'adminpanel/partials/_appointments_table.html', {
            'appointments': result['appointments'],
            'total': result['total'],
            'has_more': result['has_more'],
            'current_page': page,
        })

    return render(request, 'adminpanel/appointments_list.html', {
        'appointments': result['appointments'],
        'total': result['total'],
        'has_more': result['has_more'],
        'current_page': page,
        'filters': {
            'status': status,
            'type': appointment_type,
            'search': search,
        }
    })


@admin_required
def appointments_export(request):
    """Export appointments to CSV."""
    status = request.GET.get('status', '')
    appointment_type = request.GET.get('type', '')

    result = selectors.get_appointments_filtered(
        status=status or None,
        appointment_type=appointment_type or None,
        limit=10000
    )

    csv_content = services.export_appointments_csv(result['appointments'])
    ip_address = services.get_client_ip(request)
    services.log_export(request.user, 'appointments', result['total'], ip_address)

    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="appointments_export.csv"'
    return response


# ============ FINANCIAL OVERVIEW ============

@admin_required
def financial_overview(request):
    """Financial overview with revenue and pricing."""
    pricing = selectors.get_pricing_overview()
    type_usage = selectors.get_appointment_type_usage()
    revenue_summary = selectors.get_revenue_summary()
    top_doctors = selectors.get_revenue_potential_by_doctor(limit=10)

    return render(request, 'adminpanel/financial_overview.html', {
        'pricing': pricing,
        'type_usage': type_usage,
        'revenue_summary': revenue_summary,
        'top_doctors': top_doctors,
    })


# ============ AUDIT LOGS ============

@admin_required
def audit_logs(request):
    """View audit logs (slot changes and admin actions)."""
    log_type = request.GET.get('type', 'admin')
    page = int(request.GET.get('page', 1))

    if log_type == 'slots':
        result = selectors.get_slot_change_logs(limit=50, offset=(page - 1) * 50)
        logs = result['logs']
        total = result['total']
    else:
        result = selectors.get_admin_activity_logs(limit=50, offset=(page - 1) * 50)
        logs = result['logs']
        total = result['total']

    if request.headers.get('HX-Request'):
        template = 'adminpanel/partials/_slot_change_logs.html' if log_type == 'slots' else 'adminpanel/partials/_admin_activity_logs.html'
        return render(request, template, {
            'logs': logs,
            'total': total,
            'current_page': page,
        })

    return render(request, 'adminpanel/audit_logs.html', {
        'logs': logs,
        'total': total,
        'log_type': log_type,
        'current_page': page,
    })


# ============ DOCTOR SLOT MANAGEMENT ============

@admin_required
def admin_doctor_manage(request, doctor_id):
    """Admin view: Manage a doctor's slots and availability."""
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    ip_address = services.get_client_ip(request)

    # Log this view
    services.log_admin_action(
        admin=request.user,
        action_type='doctor_management_viewed',
        target_user=doctor.user,
        description=f'Viewed management page for Dr. {doctor.user.get_display_name()}',
        ip_address=ip_address,
    )

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

    # Get slots for the week
    slots = selectors.get_doctor_slots_for_admin(doctor_id, start_of_week, end_of_week)

    # Get availability windows
    windows = selectors.get_doctor_availability_windows_for_admin(doctor_id)

    # Get doctor statistics
    stats = selectors.get_doctor_statistics(doctor_id)

    return render(request, 'adminpanel/doctor_manage.html', {
        'doctor': doctor,
        'stats': stats,
        'slots': slots,
        'windows': windows,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week.strftime('%Y-%m-%d'),
        'next_week': next_week.strftime('%Y-%m-%d'),
        'week_dates': week_dates,
        'today': timezone.now().date(),
    })


@admin_required
@require_GET
def admin_doctor_calendar(request, doctor_id):
    """HTMX: Get calendar slots for admin management."""
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)

    # Get week from query params
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

    slots = selectors.get_doctor_slots_for_admin(doctor_id, start_of_week, end_of_week)

    return render(request, 'adminpanel/partials/_admin_calendar_grid.html', {
        'doctor': doctor,
        'slots': slots,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week.strftime('%Y-%m-%d'),
        'next_week': next_week.strftime('%Y-%m-%d'),
        'week_dates': week_dates,
        'today': timezone.now().date(),
    })


@admin_required
@require_POST
def admin_block_slot(request, slot_id):
    """Admin: Block a slot."""
    ip_address = services.get_client_ip(request)
    reason = request.POST.get('reason', '')

    try:
        slot = services.admin_block_slot(slot_id, request.user, reason, ip_address)
        messages.success(request, 'Slot blocked successfully.')

        if request.headers.get('HX-Request'):
            return admin_doctor_calendar(request, slot.doctor.id)

    except ValueError as e:
        messages.error(request, str(e))

    return redirect('adminpanel:doctor_manage', doctor_id=Slot.objects.get(id=slot_id).doctor.id)


@admin_required
@require_POST
def admin_unblock_slot(request, slot_id):
    """Admin: Unblock a slot."""
    ip_address = services.get_client_ip(request)

    try:
        slot = services.admin_unblock_slot(slot_id, request.user, ip_address)
        messages.success(request, 'Slot unblocked successfully.')

        if request.headers.get('HX-Request'):
            return admin_doctor_calendar(request, slot.doctor.id)

    except ValueError as e:
        messages.error(request, str(e))

    return redirect('adminpanel:doctor_manage', doctor_id=Slot.objects.get(id=slot_id).doctor.id)


@admin_required
@require_POST
def admin_delete_slot(request, slot_id):
    """Admin: Delete an unbooked slot."""
    ip_address = services.get_client_ip(request)
    slot = get_object_or_404(Slot, id=slot_id)
    doctor_id = slot.doctor.id

    try:
        services.admin_delete_slot(slot_id, request.user, ip_address)
        messages.success(request, 'Slot deleted successfully.')

        if request.headers.get('HX-Request'):
            return admin_doctor_calendar(request, doctor_id)

    except ValueError as e:
        messages.error(request, str(e))

    return redirect('adminpanel:doctor_manage', doctor_id=doctor_id)


@admin_required
@require_POST
def admin_create_slot(request, doctor_id):
    """Admin: Create a slot for a doctor."""
    ip_address = services.get_client_ip(request)

    date = request.POST.get('date')
    start_time = request.POST.get('start_time')
    end_time = request.POST.get('end_time')
    appointment_type = request.POST.get('appointment_type', 'video')
    is_urgent = request.POST.get('is_urgent') == 'on'
    notes = request.POST.get('notes', '')

    try:
        start_datetime = timezone.make_aware(
            datetime.strptime(f"{date} {start_time}", '%Y-%m-%d %H:%M')
        )
        end_datetime = timezone.make_aware(
            datetime.strptime(f"{date} {end_time}", '%Y-%m-%d %H:%M')
        )

        services.admin_create_slot(
            doctor_id=doctor_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            appointment_type=appointment_type,
            admin=request.user,
            is_urgent=is_urgent,
            notes=notes,
            ip_address=ip_address
        )
        messages.success(request, 'Slot created successfully.')

        if request.headers.get('HX-Request'):
            return admin_doctor_calendar(request, doctor_id)

    except ValueError as e:
        messages.error(request, str(e))

    return redirect('adminpanel:doctor_manage', doctor_id=doctor_id)


# ============ PATIENT MANAGEMENT ============

@admin_required
def admin_patient_manage(request, patient_id):
    """Admin view: Manage a patient's appointments."""
    user = get_object_or_404(User, id=patient_id, role='patient')
    ip_address = services.get_client_ip(request)

    # Log this view
    services.log_admin_action(
        admin=request.user,
        action_type='patient_management_viewed',
        target_user=user,
        description=f'Viewed management page for {user.get_display_name()}',
        ip_address=ip_address,
    )

    result = selectors.get_patient_detail_for_admin(patient_id)

    return render(request, 'adminpanel/patient_manage.html', result)


@admin_required
@require_POST
def admin_cancel_appointment(request, appointment_id):
    """Admin: Cancel an appointment."""
    ip_address = services.get_client_ip(request)
    reason = request.POST.get('reason', '')
    appointment = get_object_or_404(Appointment, id=appointment_id)
    patient_id = appointment.patient.id

    try:
        services.admin_cancel_appointment(appointment_id, request.user, reason, ip_address)
        messages.success(request, 'Appointment cancelled successfully.')
    except ValueError as e:
        messages.error(request, str(e))

    if request.headers.get('HX-Request'):
        result = selectors.get_patient_detail_for_admin(patient_id)
        return render(request, 'adminpanel/partials/_patient_appointments.html', result)

    return redirect('adminpanel:patient_manage', patient_id=patient_id)


# ============ BULK DOCTOR OPERATIONS ============

@admin_required
@require_POST
def bulk_verify_doctors_view(request):
    """Bulk verify multiple doctors."""
    doctor_ids = request.POST.getlist('doctor_ids')
    if not doctor_ids:
        messages.error(request, 'No doctors selected.')
        return redirect('adminpanel:verification_queue')

    try:
        count = services.bulk_verify_doctors(
            doctor_ids=[int(d) for d in doctor_ids],
            admin=request.user,
            ip_address=services.get_client_ip(request)
        )
        messages.success(request, f'{count} doctors verified successfully.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('adminpanel:verification_queue')


@admin_required
@require_POST
def bulk_reject_doctors_view(request):
    """Bulk reject multiple doctors."""
    doctor_ids = request.POST.getlist('doctor_ids')
    reason = request.POST.get('reason', '')

    if not doctor_ids:
        messages.error(request, 'No doctors selected.')
        return redirect('adminpanel:verification_queue')

    try:
        count = services.bulk_reject_doctors(
            doctor_ids=[int(d) for d in doctor_ids],
            reason=reason,
            admin=request.user,
            ip_address=services.get_client_ip(request)
        )
        messages.success(request, f'{count} doctors rejected.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('adminpanel:verification_queue')


# ============ WAITLIST OVERVIEW ============

@admin_required
def waitlist_overview(request):
    """Admin view: Waitlist overview per doctor."""
    waitlist_data = selectors.get_waitlist_overview()
    return render(request, 'adminpanel/waitlist_overview.html', {
        'waitlist_data': waitlist_data,
    })


# ============ REFERRAL TRACKING ============

@admin_required
def referral_tracking(request):
    """Admin view: Referral conversion tracking."""
    stats = selectors.get_referral_tracking()
    return render(request, 'adminpanel/referral_tracking.html', {
        'stats': stats,
    })


# ============ HEALTH RECORD LOGS ============

@admin_required
def health_record_logs(request):
    """Admin view: HIPAA health record access audit logs."""
    page = int(request.GET.get('page', 1))
    offset = (page - 1) * 50
    data = selectors.get_health_record_access_logs(limit=50, offset=offset)
    return render(request, 'adminpanel/health_record_logs.html', {
        'logs': data['logs'],
        'total': data['total'],
        'page': page,
        'has_more': data['has_more'],
    })


# ============ INSURANCE BREAKDOWN ============

@admin_required
def insurance_breakdown(request):
    """Admin view: Insurance provider breakdown."""
    from apps.scheduling.selectors import get_insurance_breakdown_for_admin
    breakdown = get_insurance_breakdown_for_admin()
    return render(request, 'adminpanel/insurance_breakdown.html', {
        'breakdown': breakdown,
    })


# ============ ADMIN REFUND ============

@admin_required
@require_POST
def admin_refund_appointment(request, appointment_id):
    """Admin processes refund for an appointment."""
    reason_text = request.POST.get('reason_text', '')
    try:
        refund = services.admin_process_refund(
            appointment_id=appointment_id,
            admin=request.user,
            reason='appointment_cancelled',
            reason_text=reason_text,
            ip_address=services.get_client_ip(request)
        )
        messages.success(request, f'Refund of ${refund.amount} processed successfully.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Refund failed: {str(e)}')

    return redirect('adminpanel:patient_manage', patient_id=request.POST.get('patient_id', 0))


# ============ ORGANIZATION REVIEW (PLATFORM STAFF) ============

from apps.accounts.models import Organization, OrganizationMembership
from apps.accounts.permissions import is_platform_staff


def _require_platform_staff(request):
    if not is_platform_staff(request.user):
        raise HttpResponseForbidden("Platform staff only.")


def _platform_forbidden(request):
    from django.core.exceptions import PermissionDenied
    if not is_platform_staff(request.user):
        raise PermissionDenied


@login_required
def organization_list(request):
    _platform_forbidden(request)
    status_filter = request.GET.get('status', '')
    orgs = Organization.objects.select_related('created_by').order_by('-created_at')
    if status_filter:
        orgs = orgs.filter(status=status_filter)
    return render(request, 'adminpanel/organizations/list.html', {
        'orgs': orgs,
        'status_filter': status_filter,
        'pending_count': Organization.objects.filter(status='pending').count(),
        'statuses': Organization.STATUS_CHOICES,
    })


@login_required
def organization_detail(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    memberships = OrganizationMembership.objects.filter(
        organization=org,
    ).select_related('user').order_by('-is_active', 'role', 'user__first_name')
    return render(request, 'adminpanel/organizations/detail.html', {
        'org': org,
        'memberships': memberships,
    })


@login_required
@require_POST
def organization_approve(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    org.status = 'active'
    org.approved_by = request.user
    org.approved_at = timezone.now()
    org.save(update_fields=['status', 'approved_by', 'approved_at'])
    _notify_org_owner_status(org, 'approved')
    services.log_admin_action(request.user, 'org_approved', description=f"Approved: {org.name}")
    messages.success(request, f"{org.name} approved.")
    return redirect('adminpanel:organization_list')


@login_required
@require_POST
def organization_reject(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    reason = request.POST.get('reason', '').strip()
    org.status = 'rejected'
    org.rejected_reason = reason
    org.save(update_fields=['status', 'rejected_reason'])
    _notify_org_owner_status(org, 'rejected', reason=reason)
    services.log_admin_action(request.user, 'org_rejected', description=f"Rejected: {org.name} - {reason}")
    messages.warning(request, f"{org.name} rejected.")
    return redirect('adminpanel:organization_list')


@login_required
@require_POST
def organization_suspend(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    org.status = 'suspended'
    org.save(update_fields=['status'])
    services.log_admin_action(request.user, 'org_suspended', description=f"Suspended: {org.name}")
    messages.warning(request, f"{org.name} suspended.")
    return redirect('adminpanel:organization_list')


@login_required
@require_POST
def organization_reactivate(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    org.status = 'active'
    org.save(update_fields=['status'])
    services.log_admin_action(request.user, 'org_reactivated', description=f"Reactivated: {org.name}")
    messages.success(request, f"{org.name} reactivated.")
    return redirect('adminpanel:organization_list')


@login_required
@require_POST
def organization_needs_info(request, org_id):
    _platform_forbidden(request)
    org = get_object_or_404(Organization, id=org_id)
    message = request.POST.get('message', '').strip()
    org.status = 'needs_info'
    org.save(update_fields=['status'])
    _notify_org_owner_status(org, 'needs_info', reason=message)
    services.log_admin_action(request.user, 'org_needs_info', description=f"Requested info from: {org.name}")
    messages.info(request, f"Requested more info from {org.name}.")
    return redirect('adminpanel:organization_list')


@login_required
def org_member_detail(request, org_id, membership_id):
    _platform_forbidden(request)
    from apps.accounts.models import Organization, OrganizationMembership, ProviderOrganizationProfile
    from apps.scheduling.models import Appointment

    org = get_object_or_404(Organization, id=org_id)
    membership = get_object_or_404(
        OrganizationMembership.objects.select_related('user', 'invited_by'),
        id=membership_id, organization=org,
    )

    provider_profile = None
    appointments = []
    if membership.role == 'doctor':
        provider_profile = ProviderOrganizationProfile.objects.filter(
            membership=membership,
        ).first()
        appointments = Appointment.objects.filter(
            slot__doctor__user=membership.user,
            organization=org,
        ).select_related('patient', 'slot').order_by('-slot__start_datetime')[:10]

    return render(request, 'adminpanel/organizations/member_detail.html', {
        'org': org,
        'membership': membership,
        'member': membership.user,
        'provider_profile': provider_profile,
        'recent_appointments': appointments,
        'role_choices': OrganizationMembership.ROLE_CHOICES,
    })


@login_required
@require_POST
def org_member_toggle_membership(request, org_id, membership_id):
    _platform_forbidden(request)
    from apps.accounts.models import Organization, OrganizationMembership
    org = get_object_or_404(Organization, id=org_id)
    membership = get_object_or_404(OrganizationMembership, id=membership_id, organization=org)
    membership.is_active = not membership.is_active
    membership.save(update_fields=['is_active'])
    action = 'activated' if membership.is_active else 'deactivated'
    services.log_admin_action(
        request.user, 'membership_toggled',
        description=f"Membership {action}: {membership.user.email} in {org.name}",
    )
    messages.success(request, f"Membership {action}.")
    return redirect('adminpanel:org_member_detail', org_id=org_id, membership_id=membership_id)


@login_required
@require_POST
def org_member_toggle_account(request, org_id, membership_id):
    _platform_forbidden(request)
    from apps.accounts.models import Organization, OrganizationMembership
    org = get_object_or_404(Organization, id=org_id)
    membership = get_object_or_404(OrganizationMembership, id=membership_id, organization=org)
    user = membership.user
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    action = 'enabled' if user.is_active else 'disabled'
    services.log_admin_action(
        request.user, 'user_toggled',
        description=f"Account {action}: {user.email}",
    )
    messages.success(request, f"Account {action}.")
    return redirect('adminpanel:org_member_detail', org_id=org_id, membership_id=membership_id)


@login_required
@require_POST
def org_member_change_role(request, org_id, membership_id):
    _platform_forbidden(request)
    from apps.accounts.models import Organization, OrganizationMembership
    org = get_object_or_404(Organization, id=org_id)
    membership = get_object_or_404(OrganizationMembership, id=membership_id, organization=org)
    new_role = request.POST.get('role', '').strip()
    valid_roles = [r[0] for r in OrganizationMembership.ROLE_CHOICES]
    if new_role not in valid_roles:
        messages.error(request, "Invalid role.")
        return redirect('adminpanel:org_member_detail', org_id=org_id, membership_id=membership_id)
    old_role = membership.role
    membership.role = new_role
    membership.save(update_fields=['role'])
    services.log_admin_action(
        request.user, 'membership_role_changed',
        description=f"Role changed {old_role} -> {new_role}: {membership.user.email} in {org.name}",
    )
    messages.success(request, f"Role changed to {new_role}.")
    return redirect('adminpanel:org_member_detail', org_id=org_id, membership_id=membership_id)


def _notify_org_owner_status(org, action, reason=''):
    from apps.accounts.services import create_notification
    messages_map = {
        'approved': ('Organization Approved', f"Your organization {org.name} has been approved on MedConsult. You can now invite staff."),
        'rejected': ('Organization Rejected', f"Your organization {org.name} was not approved. Reason: {reason}"),
        'needs_info': ('More Information Required', f"Your organization {org.name} registration needs more information: {reason}"),
    }
    title, body = messages_map.get(action, ('Organization Update', f"Status for {org.name} updated to {action}."))
    for membership in OrganizationMembership.objects.filter(
        organization=org, role='hospital_owner', is_active=True,
    ).select_related('user'):
        create_notification(
            membership.user, f'org_{action}', title, body,
            link=f'/org/{org.slug}/',
        )
