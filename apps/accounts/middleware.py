from django.shortcuts import redirect
from django.urls import reverse

_EXEMPT_PREFIXES = (
    '/account/',   # django-two-factor-auth routes
    '/auth/',
    '/admin/',
    '/static/',
    '/media/',
    '/api/',
)


class EnforceTwoFactorMiddleware:
    """Redirect doctors and admins to 2FA setup if not OTP-verified."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and getattr(user, 'role', None) in ('doctor', 'admin')
            and not any(request.path.startswith(p) for p in _EXEMPT_PREFIXES)
        ):
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
