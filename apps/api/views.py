"""
DRF API views for MedConsult.
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.selectors import get_filtered_doctors
from apps.accounts.models import Notification
from apps.scheduling.selectors import (
    get_available_slots_for_doctor,
    get_patient_appointments,
    get_upcoming_patient_appointments,
)
from apps.scheduling.services import book_appointment as svc_book_appointment
from apps.scheduling.models import Slot

from .serializers import (
    DoctorProfileSerializer, SlotSerializer,
    AppointmentSerializer, NotificationSerializer,
)
from .permissions import IsPatient, IsDoctor


class DoctorListAPIView(generics.ListAPIView):
    """GET /api/v1/doctors/ — List verified doctors with optional filters."""
    serializer_class = DoctorProfileSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        params = self.request.query_params
        return get_filtered_doctors(
            search=params.get('search'),
            specialization=params.get('specialization'),
            min_rating=int(params['min_rating']) if params.get('min_rating') else None,
            min_experience=int(params['min_experience']) if params.get('min_experience') else None,
            max_price=float(params['max_price']) if params.get('max_price') else None,
            sort_by=params.get('sort_by', 'rating'),
            language=params.get('language'),
            offers_second_opinions=True if params.get('second_opinion') == 'true' else None,
            available_today=params.get('available_today') == 'true',
        )


class DoctorSlotsAPIView(generics.ListAPIView):
    """GET /api/v1/doctors/<id>/slots/ — List available slots for a doctor."""
    serializer_class = SlotSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        from apps.accounts.models import DoctorProfile
        doctor = DoctorProfile.objects.get(id=self.kwargs['doctor_id'])
        return get_available_slots_for_doctor(doctor)


@api_view(['POST'])
@permission_classes([IsPatient])
def book_appointment_api(request, slot_id):
    """POST /api/v1/slots/<id>/book/ — Book a slot."""
    try:
        slot = Slot.objects.get(id=slot_id)
    except Slot.DoesNotExist:
        return Response({'error': 'Slot not found.'}, status=status.HTTP_404_NOT_FOUND)

    reason = request.data.get('reason', '')
    is_second_opinion = request.data.get('is_second_opinion', False)

    try:
        appointment = svc_book_appointment(slot, request.user, reason)
        if is_second_opinion:
            appointment.is_second_opinion = True
            appointment.save(update_fields=['is_second_opinion'])
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PatientAppointmentsAPIView(generics.ListAPIView):
    """GET /api/v1/appointments/ — List patient's appointments."""
    serializer_class = AppointmentSerializer
    permission_classes = [IsPatient]

    def get_queryset(self):
        status_filter = self.request.query_params.get('status')
        return get_patient_appointments(self.request.user, status=status_filter)


class NotificationListAPIView(generics.ListAPIView):
    """GET /api/v1/notifications/ — List user notifications."""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read_api(request, notif_id):
    """POST /api/v1/notifications/<id>/read/ — Mark notification as read."""
    try:
        notif = Notification.objects.get(id=notif_id, user=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        return Response({'success': True})
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found.'}, status=status.HTTP_404_NOT_FOUND)
