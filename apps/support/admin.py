from django.contrib import admin
from .models import FAQ, ContactMessage


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    search_fields = ('question', 'answer')
    ordering = ('order', 'created_at')


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'email', 'name', 'is_resolved', 'created_at')
    list_filter = ('is_resolved',)
    list_editable = ('is_resolved',)
    search_fields = ('email', 'name', 'subject', 'message')
    readonly_fields = ('name', 'email', 'subject', 'message', 'user', 'created_at')
    ordering = ('-created_at',)
