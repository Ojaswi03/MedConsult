"""
Context processors for adminpanel app.
"""
from apps.accounts.models import DoctorProfile
from apps.accounts.permissions import is_platform_staff


def admin_context(request):
    """Add admin-specific context to all templates."""
    if request.user.is_authenticated and is_platform_staff(request.user):
        return {
            'pending_verification_count': DoctorProfile.objects.filter(
                verification_status='pending'
            ).count()
        }
    return {}
