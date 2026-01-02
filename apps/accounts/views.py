"""
Views for accounts app - authentication and profile management.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import date

from .forms import (
    LoginForm,
    PatientStep1Form, PatientStep2Form, PatientStep3Form,
    PatientStep4Form, PatientStep5Form,
    DoctorStep1Form, DoctorStep2Form, DoctorStep3Form,
    DoctorStep4Form, DoctorStep5Form, DoctorStep6Form,
    PatientProfileForm, DoctorProfileForm,
)
from .services import (
    create_patient_from_wizard,
    create_doctor_from_wizard,
    clear_signup_session,
)
from .selectors import get_user_profile


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
                    login(request, user, backend='apps.accounts.backends.EmailOrUsernameBackend')
                    messages.success(request, 'Account created successfully! Welcome to MedConsult.')
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
                    login(request, user, backend='apps.accounts.backends.EmailOrUsernameBackend')
                    messages.success(request, 'Account created! Your profile is pending verification.')
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
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_display_name()}!')

                # Redirect based on next parameter or default
                next_url = request.GET.get('next', 'dashboard:home')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid username/email or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


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
        if request.user.role == 'patient':
            form = PatientProfileForm(request.POST, instance=profile)
        elif request.user.role == 'doctor':
            form = DoctorProfileForm(request.POST, instance=profile)
        else:
            messages.error(request, 'Invalid user role.')
            return redirect('profile')

        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        if request.user.role == 'patient':
            form = PatientProfileForm(instance=profile)
        elif request.user.role == 'doctor':
            form = DoctorProfileForm(instance=profile)
        else:
            form = None

    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'form': form
    })


@login_required
def settings_view(request):
    """User settings page."""
    return render(request, 'accounts/settings.html')
