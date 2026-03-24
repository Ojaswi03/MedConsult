"""
DRF serializers for MedConsult API.
"""
from rest_framework import serializers
from apps.accounts.models import User, DoctorProfile, Notification
from apps.scheduling.models import Slot, Appointment


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'phone']
        read_only_fields = ['id', 'role']


class DoctorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = [
            'id', 'user', 'specialization', 'years_of_experience', 'bio',
            'education', 'consultation_fee', 'languages', 'is_accepting_patients',
            'average_rating', 'review_count', 'npi_number', 'offers_second_opinions',
        ]


class SlotSerializer(serializers.ModelSerializer):
    price = serializers.SerializerMethodField()
    appointment_type_display = serializers.CharField(source='get_appointment_type_display', read_only=True)

    def get_price(self, obj):
        return str(obj.get_price())

    class Meta:
        model = Slot
        fields = [
            'id', 'start_datetime', 'end_datetime', 'appointment_type',
            'appointment_type_display', 'price', 'is_booked', 'is_blocked',
            'is_urgent', 'max_capacity', 'current_bookings',
        ]


class AppointmentSerializer(serializers.ModelSerializer):
    slot = SlotSerializer(read_only=True)
    doctor = DoctorProfileSerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'slot', 'doctor', 'reason', 'notes', 'status', 'status_display',
            'created_at', 'updated_at', 'cpt_code', 'is_second_opinion',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'notif_type', 'title', 'message', 'link', 'is_read', 'created_at']
