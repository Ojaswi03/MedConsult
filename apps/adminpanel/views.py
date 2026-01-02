"""
Views for adminpanel app - comprehensive admin dashboard.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator

from apps.accounts.models import DoctorProfile, User
from apps.scheduling.models import Appointment

from . import selectors
from . import services


def admin_required(view_func):
    """Decorator to restrict access to admin users only."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if request.user.role != 'admin':
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
