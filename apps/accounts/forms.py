from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, PatientProfile, DoctorProfile


class SignupForm(UserCreationForm):
    """User registration form."""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
    )
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
    )
    role = forms.ChoiceField(
        choices=[('patient', 'Patient'), ('doctor', 'Doctor')],
        widget=forms.RadioSelect()
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
        self.fields['password2'].widget.attrs.update({'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})


class LoginForm(AuthenticationForm):
    """User login form."""

    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500'})
    )


class PatientProfileForm(forms.ModelForm):
    """Patient profile form."""

    class Meta:
        model = PatientProfile
        fields = ['date_of_birth', 'gender', 'address', 'emergency_contact_name',
                  'emergency_contact_phone', 'medical_history', 'allergies', 'current_medications']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-4 py-2 border rounded-lg'}),
            'gender': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'address': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 3}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'medical_history': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 4}),
            'allergies': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 2}),
            'current_medications': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 2}),
        }


class DoctorProfileForm(forms.ModelForm):
    """Doctor profile form."""

    class Meta:
        model = DoctorProfile
        fields = ['medical_license_number', 'specialization', 'years_of_experience',
                  'bio', 'education', 'consultation_fee', 'is_accepting_patients']
        widgets = {
            'medical_license_number': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'specialization': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'years_of_experience': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'bio': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 4}),
            'education': forms.Textarea(attrs={'class': 'w-full px-4 py-2 border rounded-lg', 'rows': 3}),
            'consultation_fee': forms.NumberInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'is_accepting_patients': forms.CheckboxInput(attrs={'class': 'rounded'}),
        }
