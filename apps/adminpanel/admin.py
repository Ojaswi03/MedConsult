from django.contrib import admin
from .models import AdminActivityLog


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = ('admin', 'action_type', 'target_user', 'created_at', 'ip_address')
    list_filter = ('action_type', 'created_at')
    search_fields = ('admin__email', 'target_user__email', 'description')
    readonly_fields = ('admin', 'action_type', 'target_user', 'description', 'ip_address', 'metadata', 'created_at')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
