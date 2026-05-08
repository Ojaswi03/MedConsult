"""
Views for accounts app - authentication and profile management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse
from datetime import date

from .forms import (
    LoginForm,
    PatientStep1Form, PatientStep2Form, PatientStep3Form,
    PatientStep4Form, PatientStep5Form,
    DoctorStep1Form, DoctorStep2Form, DoctorStep3Form,
    DoctorStep4Form, DoctorStep5Form, DoctorStep6Form,
    PatientProfileForm, DoctorProfileForm, UserInfoForm,
)
from .services import (
    create_patient_from_wizard,
    create_doctor_from_wizard,
    clear_signup_session,
    send_verification_email,
    verify_email_token,
    send_password_reset_email,
    verify_password_reset_token,
    reset_user_password,
)
from .selectors import get_user_profile
from .models import User, Notification, Organization


def serialize_form_data(cleaned_data):
    """Convert form cleaned_data to JSON-serializable format."""
    serialized = {}
    for key, value in cleaned_data.items():
        if isinstance(value, date):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def landing_page(request):
    """Landing page for non-authenticated users."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'accounts/landing.html')


# ============ SIGNUP ROLE SELECTION ============

def signup_role_select(request):
    """Landing page to select role before signup."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'accounts/signup_role_select.html')


# ============ PATIENT SIGNUP WIZARD ============

PATIENT_STEPS = [
    ('step1', PatientStep1Form, 'Account Information'),
    ('step2', PatientStep2Form, 'Personal Details'),
    ('step3', PatientStep3Form, 'Health History'),
    ('step4', PatientStep4Form, 'Insurance Information'),
    ('step5', PatientStep5Form, 'Verification & Terms'),
]


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
@require_http_methods(["GET", "POST"])
def patient_signup_wizard(request, step=1):
    """Handle patient multi-step signup wizard."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    # Validate step number
    if step < 1 or step > len(PATIENT_STEPS):
        return redirect('patient_signup', step=1)

    step_index = step - 1
    step_name, FormClass, step_title = PATIENT_STEPS[step_index]

    # Get wizard data from session
    wizard_data = request.session.get('patient_wizard_data', {})

    # Prevent skipping steps (except step 1)
    if step > 1:
        prev_step_name = PATIENT_STEPS[step_index - 1][0]
        if prev_step_name not in wizard_data:
            return redirect('patient_signup', step=step - 1)

    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            # Store step data in session (serialize dates for JSON compatibility)
            wizard_data[step_name] = serialize_form_data(form.cleaned_data)
            request.session['patient_wizard_data'] = wizard_data
            request.session.modified = True

            if step == len(PATIENT_STEPS):
                # Final step - create user
                try:
                    user = create_patient_from_wizard(wizard_data)
                    clear_signup_session(request)

                    # Send verification email
                    send_verification_email(user, request)

                    login(request, user, backend='apps.accounts.backends.EmailOrUsernameBackend')
                    messages.success(request, 'Account created! Please check your email to verify your account.')
                    return redirect('dashboard:home')
                except Exception as e:
                    messages.error(request, f'Error creating account: {str(e)}')
                    return redirect('patient_signup', step=1)
            else:
                # Go to next step
                return redirect('patient_signup', step=step + 1)
    else:
        # Pre-fill form with existing session data
        initial_data = wizard_data.get(step_name, {})
        form = FormClass(initial=initial_data)

    context = {
        'form': form,
        'current_step': step,
        'total_steps': len(PATIENT_STEPS),
        'step_title': step_title,
        'steps': [(i + 1, s[2]) for i, s in enumerate(PATIENT_STEPS)],
        'wizard_type': 'patient',
        'has_file': False,
    }

    return render(request, 'accounts/signup_wizard.html', context)


# ============ DOCTOR SIGNUP WIZARD ============

DOCTOR_STEPS = [
    ('step1', DoctorStep1Form, 'Account Information', False),
    ('step2', DoctorStep2Form, 'Personal Details', False),
    ('step3', DoctorStep3Form, 'Professional Credentials', True),  # Has file
    ('step4', DoctorStep4Form, 'Bank Information', False),
    ('step5', DoctorStep5Form, 'Identity Verification', True),  # Has file
    ('step6', DoctorStep6Form, 'Terms & Compliance', False),
]


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
@require_http_methods(["GET", "POST"])
def doctor_signup_wizard(request, step=1):
    """Handle doctor multi-step signup wizard."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if step < 1 or step > len(DOCTOR_STEPS):
        return redirect('doctor_signup', step=1)

    step_index = step - 1
    step_name, FormClass, step_title, has_file = DOCTOR_STEPS[step_index]

    wizard_data = request.session.get('doctor_wizard_data', {})
    wizard_files = request.session.get('doctor_wizard_files', {})

    # Prevent skipping steps
    if step > 1:
        prev_step_name = DOCTOR_STEPS[step_index - 1][0]
        if prev_step_name not in wizard_data:
            return redirect('doctor_signup', step=step - 1)

    if request.method == 'POST':
        if has_file:
            form = FormClass(request.POST, request.FILES)
        else:
            form = FormClass(request.POST)

        if form.is_valid():
            # Store step data (excluding file fields, serialize dates for JSON)
            step_data = {}
            for field_name, value in form.cleaned_data.items():
                if field_name not in ['medical_license_document', 'government_id_document']:
                    if isinstance(value, date):
                        step_data[field_name] = value.isoformat()
                    else:
                        step_data[field_name] = value

            wizard_data[step_name] = step_data
            request.session['doctor_wizard_data'] = wizard_data

            # Handle file uploads - save to temporary location
            if has_file:
                for field_name in ['medical_license_document', 'government_id_document']:
                    if field_name in request.FILES:
                        uploaded_file = request.FILES[field_name]
                        # Create a unique session key if needed
                        session_key = request.session.session_key or 'temp'
                        temp_path = f'temp/signup/{session_key}/{field_name}/{uploaded_file.name}'
                        saved_path = default_storage.save(temp_path, uploaded_file)
                        wizard_files[field_name] = saved_path
                        request.session['doctor_wizard_files'] = wizard_files

            request.session.modified = True

            if step == len(DOCTOR_STEPS):
                # Final step - create user
                try:
                    # Retrieve files from storage
                    files = {}
                    for field_name, path in wizard_files.items():
                        if default_storage.exists(path):
                            files[field_name] = default_storage.open(path)

                    user = create_doctor_from_wizard(wizard_data, files)

                    # Cleanup temp files
                    for path in wizard_files.values():
                        if default_storage.exists(path):
                            default_storage.delete(path)

                    clear_signup_session(request)

                    # Send verification email
                    send_verification_email(user, request)

                    login(request, user, backend='apps.accounts.backends.EmailOrUsernameBackend')
                    messages.success(request, 'Account created! Please check your email to verify your account. Your profile is pending admin verification.')
                    return redirect('dashboard:home')
                except Exception as e:
                    messages.error(request, f'Error creating account: {str(e)}')
                    return redirect('doctor_signup', step=1)
            else:
                return redirect('doctor_signup', step=step + 1)
    else:
        initial_data = wizard_data.get(step_name, {})
        form = FormClass(initial=initial_data)

    context = {
        'form': form,
        'current_step': step,
        'total_steps': len(DOCTOR_STEPS),
        'step_title': step_title,
        'steps': [(i + 1, s[2]) for i, s in enumerate(DOCTOR_STEPS)],
        'wizard_type': 'doctor',
        'has_file': has_file,
    }

    return render(request, 'accounts/signup_wizard.html', context)


# ============ LOGIN VIEW ============

@ratelimit(key='ip', rate='10/m', method='POST', block=True)
@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login with username OR email."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data.get('identifier')
            password = form.cleaned_data.get('password')

            user = authenticate(request, username=identifier, password=password)

            if user is not None:
                if not user.is_email_verified:
                    messages.error(
                        request,
                        'Please verify your email before logging in. '
                        '<a href="/auth/resend-verification/" class="underline">Resend verification email</a>.'
                    )
                else:
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.get_display_name()}!')
                    next_url = request.GET.get('next', 'dashboard:home')
                    return redirect(next_url)
            else:
                messages.error(request, 'Invalid username/email or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


# ============ SKIP 2FA VIEW ============

@login_required
def skip_2fa(request):
    """Mark 2FA setup as skipped for this session."""
    request.session['2fa_skipped'] = True
    return redirect('dashboard:home')


# ============ LOGOUT VIEW ============

def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')


# ============ PROFILE VIEWS ============

@login_required
def profile_view(request):
    """View and edit user profile."""
    profile = get_user_profile(request.user)

    if request.method == 'POST':
        user_form = UserInfoForm(request.POST, instance=request.user)
        if request.user.role == 'patient':
            profile_form = PatientProfileForm(request.POST, instance=profile)
        elif request.user.role == 'doctor':
            profile_form = DoctorProfileForm(request.POST, instance=profile)
        else:
            profile_form = None

        forms_valid = user_form.is_valid() and (profile_form is None or profile_form.is_valid())
        if forms_valid:
            user_form.save()
            if profile_form:
                profile_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        user_form = UserInfoForm(instance=request.user)
        if request.user.role == 'patient':
            profile_form = PatientProfileForm(instance=profile)
        elif request.user.role == 'doctor':
            profile_form = DoctorProfileForm(instance=profile)
        else:
            profile_form = None

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'user_form': user_form,
        'profile_form': profile_form,
    })


@login_required
def settings_view(request):
    from django_otp import devices_for_user
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from django_otp.plugins.otp_static.models import StaticDevice

    totp_devices = TOTPDevice.objects.filter(user=request.user, confirmed=True)
    two_fa_enabled = totp_devices.exists()

    static_device = StaticDevice.objects.filter(user=request.user).first()
    backup_codes_remaining = static_device.token_set.count() if static_device else 0

    return render(request, 'accounts/settings.html', {
        'two_fa_enabled': two_fa_enabled,
        'backup_codes_remaining': backup_codes_remaining,
        'two_fa_setup_url': '/account/two_factor/setup/',
        'two_fa_disable_url': '/account/two_factor/disable/',
        'two_fa_backup_url': '/account/two_factor/backup/tokens/',
    })


@login_required
@require_POST
def regenerate_backup_codes(request):
    from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
    from django_otp.plugins.otp_totp.models import TOTPDevice

    if not TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        messages.error(request, 'Enable 2FA first before generating backup codes.')
        return redirect('settings')

    StaticDevice.objects.filter(user=request.user).delete()
    device = StaticDevice.objects.create(user=request.user, name='Backup Codes', confirmed=True)
    tokens = [StaticToken(device=device, token=StaticToken.random_token()) for _ in range(10)]
    StaticToken.objects.bulk_create(tokens)
    messages.success(request, '10 new backup codes generated. Save them somewhere safe.')
    return redirect('settings')


@login_required
@require_http_methods(["POST"])
def upload_profile_image(request):
    """Handle profile image upload."""
    if 'profile_image' not in request.FILES:
        messages.error(request, 'No image file provided.')
        return redirect('profile')

    uploaded_file = request.FILES['profile_image']

    # Validate file type
    allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
    if uploaded_file.content_type not in allowed_types:
        messages.error(request, 'Invalid file type. Please upload a PNG, JPG, or JPEG image.')
        return redirect('profile')

    # Validate file size (max 5MB)
    if uploaded_file.size > 5 * 1024 * 1024:
        messages.error(request, 'File too large. Maximum size is 5MB.')
        return redirect('profile')

    # Delete old image if exists
    if request.user.profile_image:
        request.user.profile_image.delete(save=False)

    # Save new image
    request.user.profile_image = uploaded_file
    request.user.save(update_fields=['profile_image'])

    messages.success(request, 'Profile image updated successfully!')
    return redirect('profile')


@login_required
@require_http_methods(["POST"])
def remove_profile_image(request):
    """Remove profile image."""
    if request.user.profile_image:
        request.user.profile_image.delete(save=False)
        request.user.profile_image = None
        request.user.save(update_fields=['profile_image'])
        messages.success(request, 'Profile image removed.')
    return redirect('profile')


@login_required
@require_http_methods(["POST"])
def update_theme(request):
    """Update user theme preference via HTMX."""
    theme = request.POST.get('theme', 'light')
    if theme in ['light', 'dark', 'auto']:
        request.user.theme_preference = theme
        request.user.save(update_fields=['theme_preference'])

    # Return the updated theme toggle partial
    return render(request, 'accounts/partials/_theme_toggle.html', {
        'current_theme': theme
    })


# ============ EMAIL VERIFICATION ============

def verify_email(request, token):
    """Verify email using token from verification email."""
    success, message, user = verify_email_token(token)

    if success:
        messages.success(request, message)
        if request.user.is_authenticated:
            return redirect('dashboard:home')
        return redirect('login')
    else:
        messages.error(request, message)
        if request.user.is_authenticated:
            return redirect('settings')
        return redirect('login')


@login_required
@require_http_methods(["POST"])
def resend_verification_email(request):
    """Resend verification email to current user."""
    if request.user.is_email_verified:
        messages.info(request, 'Your email is already verified.')
    else:
        send_verification_email(request.user, request)
        messages.success(request, 'Verification email sent! Please check your inbox.')

    return redirect('settings')


# ============ PASSWORD RESET ============

@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """Handle forgot password request."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        if email:
            try:
                user = User.objects.get(email=email)
                send_password_reset_email(user, request)
            except User.DoesNotExist:
                pass  # Don't reveal if email exists

            # Always show success message to prevent email enumeration
            messages.success(
                request,
                'If an account exists with this email, you will receive a password reset link shortly.'
            )
            return redirect('login')
        else:
            messages.error(request, 'Please enter your email address.')

    return render(request, 'accounts/forgot_password.html')


@require_http_methods(["GET", "POST"])
def reset_password(request, token):
    """Handle password reset using token."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    success, message, token_obj = verify_password_reset_token(token)

    if not success:
        messages.error(request, message)
        return redirect('forgot_password')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')

        if not password:
            messages.error(request, 'Please enter a new password.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif password != password_confirm:
            messages.error(request, 'Passwords do not match.')
        else:
            reset_user_password(token_obj, password)
            messages.success(request, 'Password reset successfully! You can now log in with your new password.')
            return redirect('login')

    return render(request, 'accounts/reset_password.html', {
        'token': token,
    })


# ============ NOTIFICATION VIEWS ============

@login_required
def notifications_list(request):
    """View all notifications for the current user."""
    notifications = request.user.notifications.all()[:20]
    # HTMX requests (e.g. from navbar dropdown) get a compact partial
    if request.headers.get('HX-Request'):
        return render(request, 'accounts/partials/_notifications_dropdown.html', {
            'notifications': notifications[:5],
        })
    return render(request, 'accounts/notifications.html', {
        'notifications': notifications,
    })


@login_required
@require_POST
def mark_notification_read(request, notif_id):
    """Mark a single notification as read."""
    notification = get_object_or_404(Notification, id=notif_id, user=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return HttpResponse(status=200)


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read for current user."""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return JsonResponse({'unread_count': 0})


@login_required
@require_POST
def switch_org(request):
    """Platform staff: switch active org context stored in session."""
    from apps.accounts.permissions import is_platform_staff
    from django.http import HttpResponseForbidden
    if not is_platform_staff(request.user):
        return HttpResponseForbidden()
    org_id = request.POST.get('org_id', '').strip()
    if org_id:
        org = get_object_or_404(Organization, id=org_id, status='active')
        request.session['active_organization_id'] = org.id
    else:
        request.session.pop('active_organization_id', None)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)
