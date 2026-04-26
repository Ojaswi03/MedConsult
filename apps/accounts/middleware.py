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
    Prompt all authenticated users to set up 2FA if they haven't already.
    Optional — users can skip via /auth/skip-2fa/ which sets a session flag.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and not request.session.get('2fa_skipped')
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
