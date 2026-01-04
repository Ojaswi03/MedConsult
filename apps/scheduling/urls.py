from django.urls import path
from . import views

# This URLconf will be included with namespaces 'patient' and 'doctor' in config/urls.py
# Patient routes: /patient/* -> namespace='patient'
# Doctor routes: /doctor/* -> namespace='doctor'

urlpatterns = [
    # Patient URLs
    path('doctors/', views.patient_doctors_list, name='patient_doctors_list'),
    path('doctors/<int:doctor_id>/', views.patient_doctor_detail, name='doctor_detail'),
    path('doctors/<int:doctor_id>/slots/', views.patient_slots_updates, name='patient_slots_updates'),
    path('book/<int:slot_id>/', views.patient_book_appointment, name='book_appointment'),
    path('appointments/', views.patient_appointments_list, name='patient_appointments'),
    path('appointments/<int:appointment_id>/cancel/', views.patient_cancel_appointment, name='cancel_appointment'),

    # Doctor URLs - Main Views
    path('availability/', views.doctor_availability_manage, name='doctor_availability'),
    path('schedule/', views.doctor_schedule_view, name='doctor_schedule'),
    path('generate-slots/', views.doctor_generate_slots, name='generate_slots'),

    # Doctor URLs - Availability Windows (HTMX)
    path('availability/windows/create/', views.doctor_create_availability_window, name='create_window'),
    path('availability/windows/<int:window_id>/', views.doctor_get_availability_window, name='get_window'),
    path('availability/windows/<int:window_id>/update/', views.doctor_update_availability_window, name='update_window'),
    path('availability/windows/<int:window_id>/delete/', views.doctor_delete_availability_window, name='delete_window'),

    # Doctor URLs - Slot Management (HTMX)
    path('availability/slots/create/', views.doctor_create_manual_slot, name='create_manual_slot'),
    path('availability/slots/<int:slot_id>/block/', views.doctor_block_slot, name='block_slot'),
    path('availability/slots/<int:slot_id>/unblock/', views.doctor_unblock_slot, name='unblock_slot'),
    path('availability/slots/<int:slot_id>/delete/', views.doctor_delete_slot, name='delete_slot'),
    path('availability/calendar/', views.doctor_calendar_slots, name='calendar_slots'),

    # Doctor URLs - Appointment Types
    path('availability/types/', views.doctor_appointment_type_config, name='appointment_types'),
]
