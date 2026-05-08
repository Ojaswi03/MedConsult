"""
Custom DRF permissions for MedConsult API.
"""
from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'patient'


class IsDoctor(BasePermission):
    """Verified doctors only."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == 'doctor'
            and hasattr(request.user, 'doctor_profile')
            and request.user.doctor_profile.verification_status == 'verified'
        )


class IsAdmin(BasePermission):
    """Platform staff (platform_owner or platform_admin)."""
    def has_permission(self, request, view):
        from apps.accounts.permissions import is_platform_staff
        return is_platform_staff(request.user)


class IsOrgMember(BasePermission):
    """Any active org membership."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        from apps.accounts.models import OrganizationMembership
        return OrganizationMembership.objects.filter(
            user=request.user, is_active=True,
        ).exists()


class IsOrgAdmin(BasePermission):
    """hospital_owner or hospital_admin in any active org."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        from apps.accounts.models import OrganizationMembership
        return OrganizationMembership.objects.filter(
            user=request.user, is_active=True,
            role__in=['hospital_owner', 'hospital_admin'],
        ).exists()


class IsOrgDoctor(BasePermission):
    """Verified doctor with active org membership role 'doctor'."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated or request.user.role != 'doctor':
            return False
        if not (hasattr(request.user, 'doctor_profile')
                and request.user.doctor_profile.verification_status == 'verified'):
            return False
        from apps.accounts.models import OrganizationMembership
        return OrganizationMembership.objects.filter(
            user=request.user, is_active=True, role='doctor',
        ).exists()
