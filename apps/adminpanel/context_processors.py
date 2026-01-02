"""
Context processors for adminpanel app.
"""
from apps.accounts.models import DoctorProfile


def admin_context(request):
    """Add admin-specific context to all templates."""
    if request.user.is_authenticated and request.user.role == 'admin':
        return {
            'pending_verification_count': DoctorProfile.objects.filter(
                verification_status='pending'
            ).count()
        }
    return {}
