"""
Messaging views for chat functionality.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit

from apps.scheduling.models import Appointment
from apps.accounts.models import DoctorProfile, User
from .models import Conversation
from .services import get_or_create_conversation, get_or_create_direct_conversation, send_message, mark_messages_as_read, delete_conversation_for_user
from .selectors import (
    get_user_conversations,
    get_conversation_messages,
    get_conversation_for_user,
    get_total_unread_count,
)


@login_required
def conversation_list(request):
    """
    List all conversations for the current user.
    """
    conversations = get_user_conversations(request.user)
    for conv in conversations:
        conv.other_user = conv.get_other_participant(request.user)

    return render(request, 'messaging/conversations.html', {
        'conversations': conversations,
    })


@login_required
def conversation_detail(request, conversation_id):
    """
    View a specific conversation and its messages.
    """
    conversation = get_conversation_for_user(conversation_id, request.user)

    if not conversation:
        messages.error(request, 'Conversation not found.')
        return redirect('messaging:conversations')

    # Mark messages as read
    mark_messages_as_read(conversation, request.user)

    # Get messages and annotate is_own
    chat_messages = get_conversation_messages(conversation)
    for msg in chat_messages:
        msg.is_own = msg.sender_id == request.user.id

    # Get the other participant
    other_user = conversation.get_other_participant(request.user)

    # Look up active video room for this conversation's appointment (P1-14)
    video_room = None
    if conversation.appointment_id:
        try:
            from apps.consultations.models import VideoRoom
            video_room = VideoRoom.objects.filter(
                appointment_id=conversation.appointment_id,
                status__in=['pending', 'active'],
            ).first()
        except Exception:
            pass

    return render(request, 'messaging/chat.html', {
        'conversation': conversation,
        'chat_messages': chat_messages,
        'other_user': other_user,
        'video_room': video_room,
    })


@login_required
def start_conversation(request, appointment_id):
    """
    Start or continue a conversation for an appointment.
    """
    appointment = get_object_or_404(Appointment, id=appointment_id)

    # Check if user is part of this appointment
    if request.user != appointment.patient and request.user != appointment.doctor.user:
        messages.error(request, 'You do not have access to this conversation.')
        return redirect('messaging:conversations')

    # Get or create conversation
    conversation = get_or_create_conversation(appointment)

    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
@ratelimit(key='user', rate='60/m', method='POST', block=True)
def send_message_view(request, conversation_id):
    """
    Send a message (text or file) in a conversation - HTTP fallback for non-WebSocket.
    File uploads must use this endpoint; text can also use it as fallback.
    """
    conversation = get_conversation_for_user(conversation_id, request.user)
    if not conversation:
        return JsonResponse({'error': 'Conversation not found'}, status=404)

    uploaded_file = request.FILES.get('file')
    content = request.POST.get('content', '').strip()

    if uploaded_file:
        # Validate size (10 MB max)
        if uploaded_file.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'File too large. Maximum size is 10 MB.'}, status=400)

        # Validate MIME type by extension (basic check; magic-byte validation is P2-25)
        allowed_extensions = {
            'pdf', 'doc', 'docx', 'txt',
            'jpg', 'jpeg', 'png', 'gif', 'webp',
            'mp4', 'mov',
            'xls', 'xlsx', 'csv',
        }
        ext = uploaded_file.name.rsplit('.', 1)[-1].lower() if '.' in uploaded_file.name else ''
        if ext not in allowed_extensions:
            return JsonResponse({'error': 'File type not allowed.'}, status=400)

        message = send_message(
            conversation,
            request.user,
            content=content or uploaded_file.name,
            message_type='file',
            attachment=uploaded_file,
            attachment_name=uploaded_file.name,
        )
    elif content:
        message = send_message(conversation, request.user, content)
    else:
        return JsonResponse({'error': 'Message content or file is required.'}, status=400)

    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'content': message.content,
            'message_type': message.message_type,
            'attachment_url': message.attachment.url if message.attachment else None,
            'attachment_name': message.attachment_name,
            'created_at': message.created_at.isoformat(),
        }
    })


@login_required
def get_messages(request, conversation_id):
    """
    Get messages for a conversation (AJAX endpoint).
    """
    conversation = get_conversation_for_user(conversation_id, request.user)

    if not conversation:
        return JsonResponse({'error': 'Conversation not found'}, status=404)

    before_id = request.GET.get('before_id')
    if before_id:
        before_id = int(before_id)

    messages_list = get_conversation_messages(conversation, before_id=before_id)

    return JsonResponse({
        'messages': [
            {
                'id': m.id,
                'sender_id': m.sender.id,
                'sender_name': m.sender.get_display_name(),
                'sender_initials': m.sender.get_initials(),
                'content': m.content,
                'message_type': m.message_type,
                'created_at': m.created_at.isoformat(),
                'is_read': m.is_read,
            }
            for m in messages_list
        ]
    })


@login_required
def start_direct_message(request, doctor_id=None, patient_id=None):
    """
    Start or resume a direct (no appointment) conversation.
    Patients call with doctor_id; doctors call with patient_id.
    """
    if request.user.role == 'patient':
        doctor_profile = get_object_or_404(DoctorProfile, id=doctor_id, verification_status='verified')
        patient_user = request.user
        doctor_user = doctor_profile.user
    elif request.user.role == 'doctor':
        patient_user = get_object_or_404(User, id=patient_id, role='patient')
        doctor_user = request.user
        doctor_profile = get_object_or_404(DoctorProfile, user=doctor_user)
        has_relationship = Appointment.objects.filter(
            patient=patient_user,
            doctor=doctor_profile,
        ).exists()
        if not has_relationship:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('No prior appointment relationship with this patient.')
        from apps.adminpanel.services import log_admin_action
        log_admin_action(
            admin=doctor_user,
            action_type='direct_chat_created',
            target_user=patient_user,
            description=f'Doctor {doctor_user.username} started direct chat with patient {patient_user.username}',
        )
    else:
        messages.error(request, 'Only patients and doctors can start conversations.')
        return redirect('messaging:conversations')

    conversation, _ = get_or_create_direct_conversation(patient_user, doctor_user)
    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
@require_POST
def delete_conversation(request, conversation_id):
    """
    Soft-delete a conversation for the current user.
    Admin retains all records. Conversation reappears if a new message is sent.
    """
    conversation = get_conversation_for_user(conversation_id, request.user)
    if not conversation:
        messages.error(request, 'Conversation not found.')
        return redirect('messaging:conversations')

    delete_conversation_for_user(conversation, request.user)
    return redirect('messaging:conversations')


@login_required
def unread_count(request):
    """
    Get unread message count for the current user.
    """
    count = get_total_unread_count(request.user)
    return JsonResponse({'unread_count': count})
