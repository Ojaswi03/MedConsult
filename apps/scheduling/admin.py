from django.contrib import admin
from .models import AvailabilityWindow, Slot, Appointment, AppointmentTypeConfig, SlotChangeLog


@admin.register(AvailabilityWindow)
class AvailabilityWindowAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'get_weekday_display', 'start_time', 'end_time', 'slot_duration_minutes',
                    'appointment_type', 'is_recurring', 'is_active', 'created_at')
    list_filter = ('weekday', 'is_active', 'is_recurring', 'appointment_type')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')
    fieldsets = (
        ('Doctor', {
            'fields': ('doctor',)
        }),
        ('Schedule', {
            'fields': ('weekday', 'start_time', 'end_time', 'slot_duration_minutes')
        }),
        ('Buffers', {
            'fields': ('buffer_before_minutes', 'buffer_after_minutes'),
            'classes': ('collapse',)
        }),
        ('Options', {
            'fields': ('appointment_type', 'is_recurring', 'effective_date', 'end_date', 'is_active')
        }),
    )


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'start_datetime', 'end_datetime', 'appointment_type',
                    'is_booked', 'is_blocked', 'is_urgent', 'created_at')
    list_filter = ('is_booked', 'is_blocked', 'is_urgent', 'appointment_type', 'start_datetime')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Basic Info', {
            'fields': ('doctor', 'availability_window', 'start_datetime', 'end_datetime')
        }),
        ('Status', {
            'fields': ('is_booked', 'is_blocked', 'is_urgent')
        }),
        ('Options', {
            'fields': ('appointment_type', 'max_capacity', 'current_bookings', 'notes')
        }),
    )


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'start_datetime', 'status', 'created_at')
    list_filter = ('status', 'slot__start_datetime')
    search_fields = ('patient__email', 'patient__first_name', 'patient__last_name',
                     'doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')
    readonly_fields = ('created_at', 'updated_at')

    def start_datetime(self, obj):
        return obj.start_datetime
    start_datetime.short_description = 'Start Time'


@admin.register(AppointmentTypeConfig)
class AppointmentTypeConfigAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'appointment_type', 'duration_minutes', 'price', 'is_enabled')
    list_filter = ('appointment_type', 'is_enabled')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')


@admin.register(SlotChangeLog)
class SlotChangeLogAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'slot', 'change_type', 'created_at')
    list_filter = ('change_type', 'created_at')
    search_fields = ('doctor__user__email',)
    readonly_fields = ('doctor', 'slot', 'change_type', 'created_at')
