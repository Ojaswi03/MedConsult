from django.shortcuts import redirect
from django.urls import reverse

_EXEMPT_PREFIXES = (
    '/account/',   # django-two-factor-auth routes
    '/auth/',
    '/skip-2fa/',  # 2FA skip endpoint
    '/admin/',
    '/static/',
    '/media/',
    '/api/',
)


class EnforceTwoFactorMiddleware:
    """
    Enforce 2FA for authenticated users.
    - Platform staff and any user with an elevated org membership: 2FA mandatory.
    - Patients: 2FA is optional; skip flag is honoured.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if getattr(settings, 'SKIP_2FA', False):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)
        if any(request.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return self.get_response(request)

        from apps.accounts.permissions import is_platform_staff, is_doctor, has_any_elevated_membership
        role_requires_2fa = is_platform_staff(user) or is_doctor(user) or has_any_elevated_membership(user)

        # Patients (and non-elevated org users) may skip; elevated roles cannot
        if not role_requires_2fa and request.session.get('2fa_skipped'):
            return self.get_response(request)

        is_otp_verified = getattr(user, 'is_verified', lambda: False)
        if callable(is_otp_verified):
            otp_ok = is_otp_verified()
        else:
            otp_ok = bool(is_otp_verified)

        if not otp_ok:
            from django_otp import devices_for_user
            has_device = bool(list(devices_for_user(user)))
            if has_device:
                return redirect(reverse('two_factor:login'))
            return redirect(reverse('two_factor:setup'))

        return self.get_response(request)
