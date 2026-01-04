"""
WebSocket consumers for real-time scheduling updates.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async


class DoctorCalendarConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for doctor calendar real-time updates.

    Events sent to clients:
    - slot_blocked: When a slot is blocked
    - slot_unblocked: When a slot is unblocked
    - slot_deleted: When a slot is deleted
    - slot_booked: When a slot is booked by a patient
    - window_created: When an availability window is created
    - window_updated: When an availability window is updated
    - window_deleted: When an availability window is deleted
    """

    @database_sync_to_async
    def get_doctor_profile_id(self, user):
        """Get doctor profile ID in a sync context."""
        try:
            return str(user.doctor_profile.id)
        except Exception:
            return None

    async def connect(self):
        self.doctor_id = self.scope['url_route']['kwargs']['doctor_id']
        self.group_name = f'doctor_calendar_{self.doctor_id}'

        # Verify the user is authenticated and is the doctor
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        # Check role and doctor profile using sync_to_async
        if user.role != 'doctor':
            await self.close()
            return

        doctor_profile_id = await self.get_doctor_profile_id(user)
        if doctor_profile_id != str(self.doctor_id):
            await self.close()
            return

        # Join the doctor's calendar group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming messages from WebSocket (if needed)."""
        pass

    # Event handlers for different types of updates
    async def calendar_update(self, event):
        """Send calendar update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': event['update_type'],
            'data': event['data']
        }))

    async def slot_blocked(self, event):
        """Send slot blocked notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_blocked',
            'slot_id': event['slot_id'],
            'data': event.get('data', {})
        }))

    async def slot_unblocked(self, event):
        """Send slot unblocked notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_unblocked',
            'slot_id': event['slot_id'],
            'data': event.get('data', {})
        }))

    async def slot_deleted(self, event):
        """Send slot deleted notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_deleted',
            'slot_id': event['slot_id']
        }))

    async def slot_booked(self, event):
        """Send slot booked notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_booked',
            'slot_id': event['slot_id'],
            'data': event.get('data', {})
        }))

    async def window_created(self, event):
        """Send window created notification."""
        await self.send(text_data=json.dumps({
            'type': 'window_created',
            'window_id': event['window_id'],
            'data': event.get('data', {})
        }))

    async def window_updated(self, event):
        """Send window updated notification."""
        await self.send(text_data=json.dumps({
            'type': 'window_updated',
            'window_id': event['window_id'],
            'data': event.get('data', {})
        }))

    async def window_deleted(self, event):
        """Send window deleted notification."""
        await self.send(text_data=json.dumps({
            'type': 'window_deleted',
            'window_id': event['window_id']
        }))


class PatientSlotsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for patient slot availability updates.

    Patients connect to this to receive real-time updates about
    a doctor's available slots (when slots become available/unavailable).

    Events sent to clients:
    - slots_update: HTML partial with updated slots
    - slot_taken: When a slot they were viewing is booked
    - slot_available: When a previously booked slot becomes available
    """

    async def connect(self):
        self.doctor_id = self.scope['url_route']['kwargs']['doctor_id']
        self.group_name = f'patient_slots_{self.doctor_id}'

        # Allow any authenticated user to view doctor's slots
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        # Join the patient slots group for this doctor
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming messages from WebSocket (if needed)."""
        pass

    # Event handlers
    async def slots_update(self, event):
        """Send slots update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'slots_update',
            'html': event.get('html', ''),
            'date': event.get('date', '')
        }))

    async def slot_taken(self, event):
        """Send slot taken notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_taken',
            'slot_id': event['slot_id']
        }))

    async def slot_available(self, event):
        """Send slot available notification."""
        await self.send(text_data=json.dumps({
            'type': 'slot_available',
            'slot_id': event['slot_id'],
            'data': event.get('data', {})
        }))


# Helper functions for broadcasting from views/services
async def broadcast_to_doctor_calendar(doctor_id, event_type, data):
    """
    Broadcast an update to a doctor's calendar WebSocket group.

    Args:
        doctor_id: The doctor profile ID
        event_type: The type of event (e.g., 'slot_blocked', 'window_deleted')
        data: Dict of data to send with the event
    """
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    await channel_layer.group_send(
        f'doctor_calendar_{doctor_id}',
        {
            'type': event_type,
            **data
        }
    )


async def broadcast_to_patient_slots(doctor_id, event_type, data):
    """
    Broadcast an update to patients viewing a doctor's slots.

    Args:
        doctor_id: The doctor profile ID
        event_type: The type of event (e.g., 'slot_taken', 'slots_update')
        data: Dict of data to send with the event
    """
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    await channel_layer.group_send(
        f'patient_slots_{doctor_id}',
        {
            'type': event_type,
            **data
        }
    )


# Synchronous wrappers for use in views/services
def sync_broadcast_to_doctor_calendar(doctor_id, event_type, data):
    """Synchronous wrapper for broadcasting to doctor calendar."""
    import asyncio
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    async def _send():
        await channel_layer.group_send(
            f'doctor_calendar_{doctor_id}',
            {
                'type': event_type,
                **data
            }
        )

    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        asyncio.ensure_future(_send())
    else:
        loop.run_until_complete(_send())


def sync_broadcast_to_patient_slots(doctor_id, event_type, data):
    """Synchronous wrapper for broadcasting to patient slots."""
    import asyncio
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()

    async def _send():
        await channel_layer.group_send(
            f'patient_slots_{doctor_id}',
            {
                'type': event_type,
                **data
            }
        )

    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        asyncio.ensure_future(_send())
    else:
        loop.run_until_complete(_send())
