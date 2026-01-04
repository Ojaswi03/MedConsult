"""
Messaging selectors for read operations.
"""
from django.db.models import Q, Count, Max
from .models import Conversation, Message


def get_user_conversations(user):
    """
    Get all conversations for a user.
    """
    return Conversation.objects.filter(
        Q(patient=user) | Q(doctor=user)
    ).select_related(
        'appointment',
        'appointment__slot',
        'patient',
        'doctor',
        'doctor__doctor_profile',
    ).prefetch_related(
        'messages'
    ).annotate(
        unread_count=Count(
            'messages',
            filter=Q(messages__is_read=False) & ~Q(messages__sender=user)
        )
    ).order_by('-last_message_at', '-created_at')


def get_conversation_messages(conversation, limit=50, before_id=None):
    """
    Get messages for a conversation with pagination.
    """
    messages = conversation.messages.select_related('sender')

    if before_id:
        messages = messages.filter(id__lt=before_id)

    return messages.order_by('-created_at')[:limit][::-1]


def get_conversation_for_user(conversation_id, user):
    """
    Get a specific conversation if user is a participant.
    """
    try:
        return Conversation.objects.select_related(
            'appointment',
            'appointment__slot',
            'patient',
            'doctor',
        ).get(
            Q(patient=user) | Q(doctor=user),
            id=conversation_id
        )
    except Conversation.DoesNotExist:
        return None


def get_total_unread_count(user):
    """
    Get total unread message count for a user across all conversations.
    """
    return Message.objects.filter(
        Q(conversation__patient=user) | Q(conversation__doctor=user),
        is_read=False
    ).exclude(sender=user).count()
