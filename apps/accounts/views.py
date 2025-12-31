from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .forms import SignupForm, LoginForm, PatientProfileForm, DoctorProfileForm
from .services import create_user_with_profile, update_patient_profile, update_doctor_profile
from .selectors import get_user_profile


def landing_page(request):
    """Landing page for non-authenticated users."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'accounts/landing.html')


@require_http_methods(["GET", "POST"])
def signup_view(request):
    """User registration."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = create_user_with_profile(
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role=form.cleaned_data['role']
            )
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard:home')
    else:
        form = SignupForm()

    return render(request, 'accounts/signup.html', {'form': form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.get_display_name()}!')
                return redirect('dashboard:home')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('landing')


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
