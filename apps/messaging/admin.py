from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'appointment', 'patient', 'doctor', 'is_active', 'last_message_at', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['patient__email', 'doctor__email']
    raw_id_fields = ['appointment', 'patient', 'doctor']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'sender', 'message_type', 'is_read', 'created_at']
    list_filter = ['message_type', 'is_read', 'created_at']
    search_fields = ['sender__email', 'content']
    raw_id_fields = ['conversation', 'sender']
