from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone

from apps.accounts.models import DoctorProfile, User
from apps.accounts.selectors import get_pending_doctor_verifications
from apps.scheduling.models import Appointment


@login_required
def doctor_verification_queue(request):
    """Admin view: Doctor verification queue."""
    if request.user.role != 'admin':
        return HttpResponseForbidden("Access denied. Admins only.")

    pending_doctors = get_pending_doctor_verifications()

    return render(request, 'adminpanel/doctor_verification.html', {
        'pending_doctors': pending_doctors
    })


@login_required
def verify_doctor(request, doctor_id):
    """Admin action: Verify a doctor."""
    if request.user.role != 'admin':
        return HttpResponseForbidden("Access denied. Admins only.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)

    if request.method == 'POST':
        doctor.verification_status = 'verified'
        doctor.verified_at = timezone.now()
        doctor.save()
        messages.success(request, f'Dr. {doctor.user.get_display_name()} verified successfully.')

    return redirect('adminpanel:verification_queue')


@login_required
def reject_doctor(request, doctor_id):
    """Admin action: Reject a doctor."""
    if request.user.role != 'admin':
        return HttpResponseForbidden("Access denied. Admins only.")

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)

    if request.method == 'POST':
        doctor.verification_status = 'rejected'
        doctor.verified_at = None
        doctor.save()
        messages.warning(request, f'Dr. {doctor.user.get_display_name()} rejected.')

    return redirect('adminpanel:verification_queue')


@login_required
def users_overview(request):
    """Admin view: All users overview."""
    if request.user.role != 'admin':
        return HttpResponseForbidden("Access denied. Admins only.")

    users = User.objects.all().order_by('-created_at')

    return render(request, 'adminpanel/users.html', {'users': users})


@login_required
def appointments_audit(request):
    """Admin view: All appointments audit log."""
    if request.user.role != 'admin':
        return HttpResponseForbidden("Access denied. Admins only.")

    appointments = Appointment.objects.all().select_related(
        'patient', 'doctor__user', 'slot'
    ).order_by('-created_at')[:100]

    return render(request, 'adminpanel/appointments_audit.html', {
        'appointments': appointments
    })
