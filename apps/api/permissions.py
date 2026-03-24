"""
Custom DRF permissions for MedConsult API.
"""
from rest_framework.permissions import BasePermission


class IsPatient(BasePermission):
    """Allow access only to patients."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'patient'


class IsDoctor(BasePermission):
    """Allow access only to verified doctors."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == 'doctor'
            and hasattr(request.user, 'doctor_profile')
            and request.user.doctor_profile.verification_status == 'verified'
        )


class IsAdmin(BasePermission):
    """Allow access only to admins."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'
