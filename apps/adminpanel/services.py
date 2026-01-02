"""
Services for adminpanel app - handles write operations with audit logging.
"""
import csv
from io import StringIO
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, DoctorProfile
from .models import AdminActivityLog


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_admin_action(admin, action_type, target_user=None, description='', ip_address=None, metadata=None):
    """Log an admin action for audit trail."""
    AdminActivityLog.objects.create(
        admin=admin,
        action_type=action_type,
        target_user=target_user,
        description=description,
        ip_address=ip_address,
        metadata=metadata or {}
    )


@transaction.atomic
def verify_doctor_with_logging(doctor_id, admin, ip_address=None):
    """Verify a doctor and log the action."""
    doctor = DoctorProfile.objects.select_related('user').get(id=doctor_id)
    doctor.verification_status = 'verified'
    doctor.verified_at = timezone.now()
    doctor.save()

    log_admin_action(
        admin=admin,
        action_type='doctor_verified',
        target_user=doctor.user,
        description=f'Verified Dr. {doctor.user.get_display_name()} ({doctor.specialization})',
        ip_address=ip_address,
        metadata={
            'doctor_id': doctor_id,
            'specialization': doctor.specialization,
            'license_number': doctor.medical_license_number,
        }
    )

    return doctor


@transaction.atomic
def reject_doctor_with_logging(doctor_id, admin, reason='', ip_address=None):
    """Reject a doctor and log the action."""
    doctor = DoctorProfile.objects.select_related('user').get(id=doctor_id)
    doctor.verification_status = 'rejected'
    doctor.verified_at = None
    doctor.save()

    log_admin_action(
        admin=admin,
        action_type='doctor_rejected',
        target_user=doctor.user,
        description=f'Rejected Dr. {doctor.user.get_display_name()}. Reason: {reason}',
        ip_address=ip_address,
        metadata={
            'doctor_id': doctor_id,
            'reason': reason,
            'specialization': doctor.specialization,
        }
    )

    return doctor


@transaction.atomic
def toggle_user_active(user_id, admin, is_active, ip_address=None):
    """Activate or deactivate a user."""
    user = User.objects.get(id=user_id)
    user.is_active = is_active
    user.save()

    action_type = 'user_activated' if is_active else 'user_deactivated'
    log_admin_action(
        admin=admin,
        action_type=action_type,
        target_user=user,
        description=f'{"Activated" if is_active else "Deactivated"} user {user.email}',
        ip_address=ip_address,
        metadata={
            'user_id': user_id,
            'role': user.role,
        }
    )

    return user


def log_user_view(admin, user, ip_address=None):
    """Log when admin views a user's details."""
    log_admin_action(
        admin=admin,
        action_type='user_viewed',
        target_user=user,
        description=f'Viewed user profile: {user.email}',
        ip_address=ip_address,
        metadata={
            'user_id': user.id,
            'role': user.role,
        }
    )


def log_document_view(admin, doctor, doc_type, ip_address=None):
    """Log when admin views a doctor's document."""
    log_admin_action(
        admin=admin,
        action_type='document_viewed',
        target_user=doctor.user,
        description=f'Viewed {doc_type} document for Dr. {doctor.user.get_display_name()}',
        ip_address=ip_address,
        metadata={
            'doctor_id': doctor.id,
            'document_type': doc_type,
        }
    )


def log_export(admin, export_type, count, ip_address=None):
    """Log when admin creates an export."""
    log_admin_action(
        admin=admin,
        action_type='export_created',
        description=f'Exported {count} {export_type} to CSV',
        ip_address=ip_address,
        metadata={
            'export_type': export_type,
            'count': count,
        }
    )


def export_users_csv(users):
    """Generate CSV export of users."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Username', 'Name', 'Role', 'Status', 'Created At'])

    for user in users:
        writer.writerow([
            user.email,
            user.username,
            user.get_display_name(),
            user.role,
            'Active' if user.is_active else 'Inactive',
            user.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return output.getvalue()


def export_appointments_csv(appointments):
    """Generate CSV export of appointments."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Patient Email', 'Patient Name', 'Doctor Email', 'Doctor Name',
                     'Date/Time', 'Type', 'Status', 'Created At'])

    for apt in appointments:
        writer.writerow([
            apt.patient.email if apt.patient else '',
            apt.patient.get_display_name() if apt.patient else '',
            apt.doctor.user.email if apt.doctor else '',
            apt.doctor.user.get_display_name() if apt.doctor else '',
            apt.slot.start_datetime.strftime('%Y-%m-%d %H:%M') if apt.slot else '',
            apt.slot.get_appointment_type_display() if apt.slot else '',
            apt.status,
            apt.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return output.getvalue()


def export_doctors_csv(doctors):
    """Generate CSV export of doctors."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Name', 'Specialization', 'License Number',
                     'Experience (years)', 'Fee', 'Status', 'Created At'])

    for doctor in doctors:
        writer.writerow([
            doctor.user.email,
            doctor.user.get_display_name(),
            doctor.specialization,
            doctor.medical_license_number,
            doctor.years_of_experience,
            doctor.consultation_fee,
            doctor.verification_status,
            doctor.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return output.getvalue()
