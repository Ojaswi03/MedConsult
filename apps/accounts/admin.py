from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PatientProfile, DoctorProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_staff', 'created_at')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_of_birth', 'gender', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('gender',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialization', 'verification_status', 'is_accepting_patients', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'specialization')
    list_filter = ('verification_status', 'is_accepting_patients', 'specialization')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['verify_doctors', 'reject_doctors']

    def verify_doctors(self, request, queryset):
        from django.utils import timezone
        queryset.update(verification_status='verified', verified_at=timezone.now())
        self.message_user(request, f"{queryset.count()} doctor(s) verified successfully.")

    def reject_doctors(self, request, queryset):
        queryset.update(verification_status='rejected', verified_at=None)
        self.message_user(request, f"{queryset.count()} doctor(s) rejected.")

    verify_doctors.short_description = "Verify selected doctors"
    reject_doctors.short_description = "Reject selected doctors"
