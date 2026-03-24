from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from apps.scheduling.selectors import (
    get_upcoming_patient_appointments,
    get_upcoming_doctor_appointments
)


@login_required
def dashboard_home(request):
    """
    Role-based dashboard home.
    Redirects to appropriate dashboard based on user role.
    """
    user = request.user

    if user.role == 'patient':
        return patient_dashboard(request)
    elif user.role == 'doctor':
        return doctor_dashboard(request)
    elif user.role == 'admin':
        return admin_dashboard(request)
    else:
        return redirect('landing')


@login_required
def patient_dashboard(request):
    """Patient dashboard - shows upcoming appointments, pending reviews, referrals, and quick actions."""
    if request.user.role != 'patient':
        return redirect('dashboard:home')

    from apps.scheduling.selectors import get_patient_dashboard_data
    dashboard_data = get_patient_dashboard_data(request.user)

    context = {
        'upcoming_appointments': dashboard_data['upcoming_appointments'],
        'pending_reviews': dashboard_data['pending_reviews'],
        'active_referrals': dashboard_data['active_referrals'],
        'recent_notifications': dashboard_data['recent_notifications'],
        'book_again_doctors': dashboard_data['book_again_doctors'],
    }
    return render(request, 'dashboard/patient_home.html', context)


@login_required
def doctor_dashboard(request):
    """Doctor dashboard - shows upcoming appointments, onboarding score, and schedule overview."""
    if request.user.role != 'doctor':
        return redirect('dashboard:home')

    doctor_profile = request.user.doctor_profile
    upcoming_appointments = get_upcoming_doctor_appointments(doctor_profile)[:10]

    context = {
        'upcoming_appointments': upcoming_appointments,
        'doctor_profile': doctor_profile,
        'onboarding_score': doctor_profile.onboarding_score,
    }
    return render(request, 'dashboard/doctor_home.html', context)


@login_required
def admin_dashboard(request):
    """Admin dashboard - shows system overview and pending actions."""
    if request.user.role != 'admin':
        return redirect('dashboard:home')

    from apps.accounts.selectors import get_pending_doctor_verifications

    pending_verifications = get_pending_doctor_verifications()[:10]

    context = {
        'pending_verifications': pending_verifications,
    }
    return render(request, 'dashboard/admin_home.html', context)
