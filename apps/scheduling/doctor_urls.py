from django.urls import path
from . import views

urlpatterns = [
    # Schedule overview
    path('schedule/', views.doctor_schedule_view, name='doctor_schedule'),

    # Availability management
    path('availability/', views.doctor_availability_manage, name='doctor_availability'),
    path('availability/calendar/', views.doctor_calendar_slots, name='calendar_slots'),
    path('availability/types/', views.doctor_appointment_type_config, name='appointment_types'),
    path('generate-slots/', views.doctor_generate_slots, name='generate_slots'),

    # Availability windows (HTMX)
    path('availability/windows/create/', views.doctor_create_availability_window, name='create_window'),
    path('availability/windows/<int:window_id>/', views.doctor_get_availability_window, name='get_window'),
    path('availability/windows/<int:window_id>/update/', views.doctor_update_availability_window, name='update_window'),
    path('availability/windows/<int:window_id>/delete/', views.doctor_delete_availability_window, name='delete_window'),

    # Slot management (HTMX)
    path('availability/slots/create/', views.doctor_create_manual_slot, name='create_manual_slot'),
    path('availability/slots/<int:slot_id>/block/', views.doctor_block_slot, name='block_slot'),
    path('availability/slots/<int:slot_id>/unblock/', views.doctor_unblock_slot, name='unblock_slot'),
    path('availability/slots/<int:slot_id>/delete/', views.doctor_delete_slot, name='delete_slot'),

    # Time off
    path('availability/time-off/', views.doctor_time_off_list, name='time_off_list'),
    path('availability/time-off/<int:block_id>/delete/', views.doctor_delete_time_off, name='delete_time_off'),

    # Availability exceptions
    path('availability/exceptions/create/', views.doctor_exception_create, name='create_exception'),
    path('availability/exceptions/<int:exception_id>/delete/', views.doctor_exception_delete, name='delete_exception'),

    # Analytics
    path('analytics/', views.doctor_analytics_view, name='doctor_analytics'),

    # Appointments
    path('appointments/<int:appointment_id>/prescription/write/', views.doctor_write_prescription, name='write_prescription'),
    path('appointments/<int:appointment_id>/followup/', views.doctor_schedule_followup, name='schedule_followup'),
    path('appointments/<int:appointment_id>/referral/', views.doctor_create_referral, name='create_referral'),

    # Patient data
    path('patients/<int:patient_id>/history/', views.doctor_patient_history, name='patient_history'),
    path('patients/<int:patient_id>/records/', views.doctor_view_shared_records, name='doctor_view_patient_records'),

    # Reviews
    path('reviews/<int:review_id>/respond/', views.doctor_respond_to_review, name='respond_to_review'),
]
