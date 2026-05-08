"""
WebSocket consumers for real-time chat.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import Conversation, Message
from .services import send_message, mark_messages_as_read


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for chat functionality.
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        self.user = self.scope['user']

        # Check if user is authenticated and can access this conversation
        if not self.user.is_authenticated:
            await self.close()
            return

        conversation = await self.get_conversation()
        if not conversation or not await self.can_access_conversation(conversation):
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Mark existing messages as read
        await self.mark_as_read(conversation)

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')

            if message_type == 'message':
                await self.handle_message(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
            elif message_type == 'read':
                await self.handle_read()

        except json.JSONDecodeError:
            pass

    async def handle_message(self, data):
        """Handle a new chat message."""
        content = data.get('content', '').strip()
        if not content:
            return

        conversation = await self.get_conversation()
        if not conversation:
            return

        # Save message to database
        message = await self.save_message(conversation, content)

        # Broadcast to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': {
                    'id': message.id,
                    'sender_id': self.user.id,
                    'sender_name': self.user.get_display_name(),
                    'sender_initials': self.user.get_initials(),
                    'content': message.content,
                    'message_type': message.message_type,
                    'created_at': message.created_at.isoformat(),
                    'is_read': message.is_read,
                }
            }
        )

    async def handle_typing(self, data):
        """Handle typing indicator."""
        is_typing = data.get('is_typing', False)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'user_name': self.user.get_display_name(),
                'is_typing': is_typing,
            }
        )

    async def handle_read(self):
        """Handle read receipt."""
        conversation = await self.get_conversation()
        if conversation:
            await self.mark_as_read(conversation)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'messages_read',
                    'user_id': self.user.id,
                    'read_at': timezone.now().isoformat(),
                }
            )

    # Event handlers for group broadcasts

    async def chat_message(self, event):
        """Send message to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
        }))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        # Don't send typing indicator to the sender
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'user_name': event['user_name'],
                'is_typing': event['is_typing'],
            }))

    async def messages_read(self, event):
        """Send read receipt to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'read',
            'user_id': event['user_id'],
            'read_at': event['read_at'],
        }))

    # Database operations

    @database_sync_to_async
    def get_conversation(self):
        try:
            return Conversation.objects.select_related('patient', 'doctor').get(
                id=self.conversation_id
            )
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def can_access_conversation(self, conversation):
        # Must be a direct participant
        if (conversation.patient_id != self.user.id
                and conversation.doctor_id != self.user.id):
            return False
        # Platform staff bypass org check
        from apps.accounts.permissions import is_platform_staff
        if is_platform_staff(self.user):
            return True
        # Org users must have an active membership in the conversation's org
        org = getattr(conversation, 'organization', None)
        if org is None:
            return True  # legacy conversations pre-migration
        from apps.accounts.models import OrganizationMembership
        if self.user.role in ('patient',):
            return True  # patients are platform-wide
        return OrganizationMembership.objects.filter(
            user=self.user, organization=org, is_active=True,
        ).exists()

    @database_sync_to_async
    def save_message(self, conversation, content):
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            content=content,
            message_type='text',
        )
        conversation.last_message_at = message.created_at
        conversation.save(update_fields=['last_message_at', 'updated_at'])
        return message

    @database_sync_to_async
    def mark_as_read(self, conversation):
        return mark_messages_as_read(conversation, self.user)
