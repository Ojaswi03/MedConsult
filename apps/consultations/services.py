"""
Video consultation services for Daily.co integration.
"""
import requests
import uuid
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import VideoRoom


def get_daily_api_headers():
    """Get headers for Daily.co API requests."""
    return {
        'Authorization': f'Bearer {settings.DAILY_API_KEY}',
        'Content-Type': 'application/json',
    }


def create_video_room(appointment):
    """
    Create a Daily.co video room for an appointment.
    """
    # Check if room already exists
    try:
        return VideoRoom.objects.get(appointment=appointment)
    except VideoRoom.DoesNotExist:
        pass

    # Generate unique room name
    room_name = f"medconsult-{appointment.id}-{uuid.uuid4().hex[:8]}"

    # Calculate room expiration (appointment end time + 1 hour buffer)
    exp_time = appointment.end_datetime + timedelta(hours=1)

    # Create room via Daily.co API
    if settings.DAILY_API_KEY:
        try:
            response = requests.post(
                'https://api.daily.co/v1/rooms',
                headers=get_daily_api_headers(),
                json={
                    'name': room_name,
                    'privacy': 'private',
                    'properties': {
                        'exp': int(exp_time.timestamp()),
                        'enable_chat': True,
                        'enable_screenshare': True,
                        'enable_recording': False,
                        'start_video_off': False,
                        'start_audio_off': False,
                    }
                },
                timeout=10
            )

            if response.status_code == 200:
                room_data = response.json()
                room_url = room_data.get('url', f'https://medconsult.daily.co/{room_name}')
            else:
                # Fallback to demo URL if API fails
                room_url = f'https://medconsult.daily.co/{room_name}'
        except requests.RequestException:
            room_url = f'https://medconsult.daily.co/{room_name}'
    else:
        # Demo mode - no API key configured
        room_url = f'https://medconsult.daily.co/{room_name}'

    # Create VideoRoom record
    video_room = VideoRoom.objects.create(
        appointment=appointment,
        daily_room_name=room_name,
        daily_room_url=room_url,
        status='pending',
    )

    return video_room


def get_meeting_token(video_room, user, is_owner=False):
    """
    Get a meeting token for a user to join the room.
    """
    if not settings.DAILY_API_KEY:
        return None

    try:
        response = requests.post(
            'https://api.daily.co/v1/meeting-tokens',
            headers=get_daily_api_headers(),
            json={
                'properties': {
                    'room_name': video_room.daily_room_name,
                    'user_name': user.get_display_name(),
                    'is_owner': is_owner,
                    'enable_screenshare': True,
                    'start_video_off': False,
                    'start_audio_off': False,
                }
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json().get('token')
    except requests.RequestException:
        pass

    return None


def start_consultation(video_room):
    """
    Mark a consultation as started.
    """
    if video_room.status == 'pending':
        video_room.status = 'active'
        video_room.started_at = timezone.now()
        video_room.save(update_fields=['status', 'started_at'])

    return video_room


def end_consultation(video_room):
    """
    Mark a consultation as ended.
    """
    if video_room.status in ['pending', 'active']:
        video_room.status = 'ended'
        video_room.ended_at = timezone.now()

        if video_room.started_at:
            duration = video_room.ended_at - video_room.started_at
            video_room.duration_minutes = int(duration.total_seconds() / 60)

        video_room.save(update_fields=['status', 'ended_at', 'duration_minutes'])

        # Delete room from Daily.co
        if settings.DAILY_API_KEY:
            try:
                requests.delete(
                    f'https://api.daily.co/v1/rooms/{video_room.daily_room_name}',
                    headers=get_daily_api_headers(),
                    timeout=10
                )
            except requests.RequestException:
                pass

    return video_room


def get_video_room_for_appointment(appointment):
    """
    Get or create a video room for an appointment.
    """
    try:
        return VideoRoom.objects.get(appointment=appointment)
    except VideoRoom.DoesNotExist:
        return None
