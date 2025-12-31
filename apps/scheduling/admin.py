from django.contrib import admin
from .models import AvailabilityWindow, Slot, Appointment


@admin.register(AvailabilityWindow)
class AvailabilityWindowAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'get_weekday_display', 'start_time', 'end_time', 'is_active', 'created_at')
    list_filter = ('weekday', 'is_active')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'start_datetime', 'end_datetime', 'is_booked', 'created_at')
    list_filter = ('is_booked', 'start_datetime')
    search_fields = ('doctor__user__email', 'doctor__user__first_name', 'doctor__user__last_name')
    readonly_fields = ('created_at',)


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
