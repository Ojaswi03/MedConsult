from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import AvailabilityWindow, Slot, AppointmentTypeConfig, AvailabilityWindowTypeConfig, APPOINTMENT_TYPE_CHOICES


# Consistent styling classes (matching accounts/forms.py)
INPUT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
INPUT_CLASS_DARK = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white'
SELECT_CLASS = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
SELECT_CLASS_DARK = 'w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white'
CHECKBOX_CLASS = 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'


class AvailabilityWindowForm(forms.ModelForm):
    """Form for creating/editing availability windows with multi-type appointment support."""

    SLOT_DURATION_CHOICES = [
        (15, '15 minutes'),
        (30, '30 minutes'),
        (45, '45 minutes'),
        (60, '60 minutes'),
    ]

    BUFFER_CHOICES = [
        (0, 'No buffer'),
        (5, '5 minutes'),
        (10, '10 minutes'),
        (15, '15 minutes'),
    ]

    slot_duration_minutes = forms.ChoiceField(
        choices=SLOT_DURATION_CHOICES,
        initial=30,
        widget=forms.Select(attrs={'class': SELECT_CLASS_DARK}),
        label='Slot Duration'
    )

    buffer_before_minutes = forms.ChoiceField(
        choices=BUFFER_CHOICES,
        initial=0,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS_DARK}),
        label='Buffer Before'
    )

    buffer_after_minutes = forms.ChoiceField(
        choices=BUFFER_CHOICES,
        initial=0,
        required=False,
        widget=forms.Select(attrs={'class': SELECT_CLASS_DARK}),
        label='Buffer After'
    )

    # Multi-type appointment fields
    type_video = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS, 'id': 'type_video'}),
        label='Video Consultation'
    )
    price_video = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS_DARK,
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        label='Price ($)'
    )

    type_chat = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS, 'id': 'type_chat'}),
        label='Chat Consultation'
    )
    price_chat = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS_DARK,
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        label='Price ($)'
    )

    type_phone = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS, 'id': 'type_phone'}),
        label='Phone Consultation'
    )
    price_phone = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS_DARK,
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        label='Price ($)'
    )

    class Meta:
        model = AvailabilityWindow
        fields = [
            'weekday',
            'start_time',
            'end_time',
            'slot_duration_minutes',
            'buffer_before_minutes',
            'buffer_after_minutes',
            'is_recurring',
            'effective_date',
            'end_date',
        ]
        widgets = {
            'weekday': forms.Select(attrs={'class': SELECT_CLASS_DARK}),
            'start_time': forms.TimeInput(attrs={
                'class': INPUT_CLASS_DARK,
                'type': 'time',
            }),
            'end_time': forms.TimeInput(attrs={
                'class': INPUT_CLASS_DARK,
                'type': 'time',
            }),
            'is_recurring': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'effective_date': forms.DateInput(attrs={
                'class': INPUT_CLASS_DARK,
                'type': 'date',
            }),
            'end_date': forms.DateInput(attrs={
                'class': INPUT_CLASS_DARK,
                'type': 'date',
            }),
        }
        labels = {
            'weekday': 'Day of Week',
            'start_time': 'Start Time',
            'end_time': 'End Time',
            'is_recurring': 'Repeat Weekly',
            'effective_date': 'Start Date (optional)',
            'end_date': 'End Date (optional)',
        }
        help_texts = {
            'is_recurring': 'If checked, this availability repeats every week',
            'effective_date': 'Leave blank to start immediately',
            'end_date': 'Leave blank for no end date',
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # If editing existing window, load type configs
        if instance and instance.pk:
            for config in instance.type_configs.all():
                type_key = config.appointment_type
                self.fields[f'type_{type_key}'].initial = config.is_enabled
                self.fields[f'price_{type_key}'].initial = config.price

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        effective_date = cleaned_data.get('effective_date')
        end_date = cleaned_data.get('end_date')

        # Check at least one appointment type is selected
        type_video = cleaned_data.get('type_video')
        type_chat = cleaned_data.get('type_chat')
        type_phone = cleaned_data.get('type_phone')

        if not any([type_video, type_chat, type_phone]):
            raise ValidationError('Please select at least one appointment type.')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

            # Check minimum slot duration
            from datetime import datetime, timedelta
            duration = datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)
            slot_duration = int(cleaned_data.get('slot_duration_minutes', 30))
            if duration.total_seconds() < slot_duration * 60:
                raise ValidationError(f'Time window must be at least {slot_duration} minutes.')

        if effective_date and end_date:
            if effective_date > end_date:
                raise ValidationError('End date must be after start date.')

        return cleaned_data

    def get_type_configs(self):
        """Return a list of (appointment_type, is_enabled, price) tuples from cleaned data."""
        if not hasattr(self, 'cleaned_data'):
            return []

        configs = []
        for type_code, type_name in APPOINTMENT_TYPE_CHOICES:
            is_enabled = self.cleaned_data.get(f'type_{type_code}', False)
            price = self.cleaned_data.get(f'price_{type_code}', Decimal('0'))
            if price is None:
                price = Decimal('0')
            configs.append((type_code, is_enabled, price))
        return configs


class ManualSlotForm(forms.Form):
    """Form for creating manual/urgent slots."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': INPUT_CLASS,
            'type': 'date',
        }),
        label='Date'
    )

    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': INPUT_CLASS,
            'type': 'time',
        }),
        label='Start Time'
    )

    end_time = forms.TimeField(
        widget=forms.TimeInput(attrs={
            'class': INPUT_CLASS,
            'type': 'time',
        }),
        label='End Time'
    )

    appointment_type = forms.ChoiceField(
        choices=APPOINTMENT_TYPE_CHOICES,
        initial='video',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        label='Appointment Type'
    )

    is_urgent = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        label='Mark as Urgent',
        help_text='Urgent slots are highlighted for patients'
    )

    max_capacity = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={'class': INPUT_CLASS}),
        label='Max Capacity',
        help_text='Set to more than 1 for group sessions'
    )

    notes = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Optional notes (e.g., "Emergency slot")',
        }),
        label='Notes'
    )

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        date = cleaned_data.get('date')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError('End time must be after start time.')

        if date:
            from django.utils import timezone
            if date < timezone.now().date():
                raise ValidationError('Cannot create slots in the past.')

        return cleaned_data


class BlockSlotForm(forms.Form):
    """Form for blocking a slot."""

    reason = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': 'Reason for blocking (optional)',
        }),
        label='Reason'
    )


class AppointmentTypeConfigForm(forms.ModelForm):
    """Form for configuring appointment type pricing."""

    class Meta:
        model = AppointmentTypeConfig
        fields = ['appointment_type', 'duration_minutes', 'price', 'is_enabled']
        widgets = {
            'appointment_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'duration_minutes': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': 15,
                'max': 120,
                'step': 15,
            }),
            'price': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': 0,
                'step': '0.01',
            }),
            'is_enabled': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }
        labels = {
            'appointment_type': 'Type',
            'duration_minutes': 'Duration (minutes)',
            'price': 'Price ($)',
            'is_enabled': 'Enabled',
        }


class AppointmentTypeConfigFormSet(forms.BaseModelFormSet):
    """FormSet for managing all appointment type configs at once."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = kwargs.get('queryset', AppointmentTypeConfig.objects.none())


# Helper function to create formset
def get_appointment_type_formset(doctor_profile, data=None):
    """Get formset for appointment type configuration."""
    AppointmentTypeFormSet = forms.modelformset_factory(
        AppointmentTypeConfig,
        form=AppointmentTypeConfigForm,
        formset=AppointmentTypeConfigFormSet,
        extra=0,
        can_delete=False
    )

    queryset = AppointmentTypeConfig.objects.filter(doctor=doctor_profile)

    # Create default configs if none exist
    if not queryset.exists():
        for type_code, type_name in APPOINTMENT_TYPE_CHOICES:
            AppointmentTypeConfig.objects.create(
                doctor=doctor_profile,
                appointment_type=type_code,
                duration_minutes=30,
                price=0,
                is_enabled=True
            )
        queryset = AppointmentTypeConfig.objects.filter(doctor=doctor_profile)

    return AppointmentTypeFormSet(data, queryset=queryset)
