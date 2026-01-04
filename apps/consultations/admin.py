from django.contrib import admin
from .models import VideoRoom


@admin.register(VideoRoom)
class VideoRoomAdmin(admin.ModelAdmin):
    list_display = ['id', 'appointment', 'status', 'started_at', 'ended_at', 'duration_minutes']
    list_filter = ['status', 'created_at']
    search_fields = ['daily_room_name', 'appointment__id']
    readonly_fields = ['daily_room_name', 'daily_room_url', 'created_at', 'started_at', 'ended_at']
