"""
Video consultation views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone

from apps.scheduling.models import Appointment
from .models import VideoRoom
from .services import (
    create_video_room,
    get_meeting_token,
    start_consultation,
    end_consultation,
    get_video_room_for_appointment,
)


@login_required
def join_consultation(request, appointment_id):
    """
    Join a video consultation for an appointment.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # Check if user is part of this appointment
    if request.user != appointment.patient and request.user != appointment.doctor.user:
        messages.error(request, 'You do not have access to this consultation.')
        return redirect('dashboard:home')

    # Check if appointment type is video
    if appointment.slot.appointment_type != 'video':
        messages.error(request, 'This appointment is not a video consultation.')
        return redirect('dashboard:home')

    # Check if appointment is today or within 15 minutes of start
    now = timezone.now()
    time_until_start = (appointment.start_datetime - now).total_seconds() / 60

    if time_until_start > 15:
        messages.warning(request, 'You can join the video call up to 15 minutes before the appointment.')
        return redirect('dashboard:home')

    if appointment.end_datetime < now:
        messages.error(request, 'This appointment has already ended.')
        return redirect('dashboard:home')

    # Get or create video room
    video_room = get_video_room_for_appointment(appointment)
    if not video_room:
        video_room = create_video_room(appointment)

    if not video_room.can_join:
        messages.error(request, 'This consultation has ended.')
        return redirect('dashboard:home')

    # Get meeting token
    is_owner = request.user == appointment.doctor.user
    meeting_token = get_meeting_token(video_room, request.user, is_owner=is_owner)

    # Mark as started if first join
    if video_room.status == 'pending':
        start_consultation(video_room)

    return render(request, 'consultations/video_room.html', {
        'appointment': appointment,
        'video_room': video_room,
        'meeting_token': meeting_token,
        'is_doctor': request.user == appointment.doctor.user,
    })


@login_required
def waiting_room(request, appointment_id):
    """
    Waiting room before joining the video consultation.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # Check if user is part of this appointment
    if request.user != appointment.patient and request.user != appointment.doctor.user:
        messages.error(request, 'You do not have access to this consultation.')
        return redirect('dashboard:home')

    return render(request, 'consultations/waiting_room.html', {
        'appointment': appointment,
    })


@login_required
@require_POST
def end_consultation_view(request, appointment_id):
    """
    End a video consultation.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # Only doctor can end the consultation
    if request.user != appointment.doctor.user:
        return JsonResponse({'error': 'Only the doctor can end the consultation.'}, status=403)

    video_room = get_video_room_for_appointment(appointment)
    if video_room:
        end_consultation(video_room)

    return JsonResponse({'success': True})


@login_required
def consultation_status(request, appointment_id):
    """
    Get the status of a video consultation.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    video_room = get_video_room_for_appointment(appointment)

    return JsonResponse({
        'has_room': video_room is not None,
        'status': video_room.status if video_room else None,
        'can_join': video_room.can_join if video_room else False,
    })
