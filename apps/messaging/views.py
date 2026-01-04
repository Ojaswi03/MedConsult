"""
Messaging views for chat functionality.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.http import JsonResponse

from apps.scheduling.models import Appointment
from .models import Conversation
from .services import get_or_create_conversation, send_message, mark_messages_as_read
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

    # Get messages
    chat_messages = get_conversation_messages(conversation)

    # Get the other participant
    other_user = conversation.get_other_participant(request.user)

    return render(request, 'messaging/chat.html', {
        'conversation': conversation,
        'messages': chat_messages,
        'other_user': other_user,
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
def send_message_view(request, conversation_id):
    """
    Send a message in a conversation (fallback for non-WebSocket).
    """
    conversation = get_conversation_for_user(conversation_id, request.user)

    if not conversation:
        return JsonResponse({'error': 'Conversation not found'}, status=404)

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Message content is required'}, status=400)

    message = send_message(conversation, request.user, content)

    return JsonResponse({
        'success': True,
        'message': {
            'id': message.id,
            'content': message.content,
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
def unread_count(request):
    """
    Get unread message count for the current user.
    """
    count = get_total_unread_count(request.user)
    return JsonResponse({'unread_count': count})
