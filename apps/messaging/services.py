"""
Messaging services for chat functionality.
"""
from django.db import transaction
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Conversation, Message


@transaction.atomic
def get_or_create_direct_conversation(patient_user, doctor_user):
    """
    Get or create a direct (non-appointment) conversation between a patient and doctor.
    Reuses an existing direct conversation if one already exists.
    """
    existing = Conversation.objects.filter(
        patient=patient_user,
        doctor=doctor_user,
        is_direct=True,
    ).first()
    if existing:
        return existing, False

    conversation = Conversation.objects.create(
        patient=patient_user,
        doctor=doctor_user,
        is_direct=True,
    )

    disclaimer = (
        "This is a direct message not linked to a scheduled appointment. "
        "Responses may be delayed. For urgent medical concerns please book an appointment "
        "or contact emergency services."
    )
    Message.objects.create(
        conversation=conversation,
        sender=doctor_user,
        content=disclaimer,
        message_type='system',
        is_read=False,
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=['last_message_at'])

    return conversation, True


@transaction.atomic
def get_or_create_conversation(appointment):
    """
    Get or create a conversation for an appointment.
    """
    conversation, created = Conversation.objects.get_or_create(
        appointment=appointment,
        defaults={
            'patient': appointment.patient,
            'doctor': appointment.doctor.user,
        }
    )

    if created:
        # Create system message
        Message.objects.create(
            conversation=conversation,
            sender=appointment.doctor.user,
            content=f"Conversation started for your appointment on {appointment.start_datetime.strftime('%B %d, %Y at %I:%M %p')}",
            message_type='system',
            is_read=True,
        )
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at'])

    return conversation


@transaction.atomic
def send_message(conversation, sender, content, message_type='text', attachment=None, attachment_name=''):
    """
    Send a message in a conversation.
    """
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
        message_type=message_type,
        attachment=attachment,
        attachment_name=attachment_name,
    )

    # Update conversation last_message_at and restore visibility for both sides
    update_fields = ['last_message_at', 'updated_at']
    conversation.last_message_at = message.created_at
    if conversation.deleted_by_patient:
        conversation.deleted_by_patient = False
        update_fields.append('deleted_by_patient')
    if conversation.deleted_by_doctor:
        conversation.deleted_by_doctor = False
        update_fields.append('deleted_by_doctor')
    conversation.save(update_fields=update_fields)

    # Broadcast message via WebSocket
    broadcast_new_message(conversation, message)

    return message


@transaction.atomic
def delete_conversation_for_user(conversation, user):
    """
    Soft-delete a conversation for a specific user.
    The conversation and all messages are retained in the database for admin records.
    If the other party sends a new message, the conversation reappears.
    """
    if user.id == conversation.patient_id:
        conversation.deleted_by_patient = True
        conversation.save(update_fields=['deleted_by_patient'])
    elif user.id == conversation.doctor_id:
        conversation.deleted_by_doctor = True
        conversation.save(update_fields=['deleted_by_doctor'])


def mark_messages_as_read(conversation, user):
    """
    Mark all unread messages in a conversation as read for a user.
    """
    unread_messages = conversation.messages.filter(
        is_read=False
    ).exclude(sender=user)

    now = timezone.now()
    updated = unread_messages.update(is_read=True, read_at=now)

    if updated > 0:
        # Broadcast read receipt
        broadcast_messages_read(conversation, user)

    return updated


def broadcast_new_message(conversation, message):
    """
    Broadcast a new message to all participants via WebSocket.
    """
    channel_layer = get_channel_layer()
    group_name = f"chat_{conversation.id}"

    message_data = {
        'type': 'chat_message',
        'message': {
            'id': message.id,
            'sender_id': message.sender.id,
            'sender_name': message.sender.get_display_name(),
            'sender_initials': message.sender.get_initials(),
            'content': message.content,
            'message_type': message.message_type,
            'created_at': message.created_at.isoformat(),
            'is_read': message.is_read,
        }
    }

    try:
        async_to_sync(channel_layer.group_send)(group_name, message_data)
    except Exception:
        pass  # Silently fail if WebSocket not available


def broadcast_messages_read(conversation, user):
    """
    Broadcast read receipt to all participants.
    """
    channel_layer = get_channel_layer()
    group_name = f"chat_{conversation.id}"

    message_data = {
        'type': 'messages_read',
        'user_id': user.id,
        'read_at': timezone.now().isoformat(),
    }

    try:
        async_to_sync(channel_layer.group_send)(group_name, message_data)
    except Exception:
        pass


def broadcast_typing_indicator(conversation, user, is_typing):
    """
    Broadcast typing indicator to other participants.
    """
    channel_layer = get_channel_layer()
    group_name = f"chat_{conversation.id}"

    message_data = {
        'type': 'typing_indicator',
        'user_id': user.id,
        'user_name': user.get_display_name(),
        'is_typing': is_typing,
    }

    try:
        async_to_sync(channel_layer.group_send)(group_name, message_data)
    except Exception:
        pass
