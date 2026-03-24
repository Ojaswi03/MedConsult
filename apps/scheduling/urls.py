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
    path('appointments/<int:appointment_id>/reschedule/', views.patient_reschedule_appointment, name='reschedule_appointment'),
    path('appointments/<int:appointment_id>/prescription/download/', views.patient_download_prescription, name='download_prescription'),

    # Patient URLs - Symptom Selector (HTMX)
    path('symptoms/body-parts/', views.get_body_parts, name='get_body_parts'),
    path('symptoms/body-parts/<int:body_part_id>/conditions/', views.get_conditions, name='get_conditions'),
    path('symptoms/list/', views.get_symptoms, name='get_symptoms'),

    # Patient URLs - Reviews
    path('reviews/', views.patient_reviews_list, name='patient_reviews'),
    path('reviews/<int:appointment_id>/submit/', views.patient_submit_review, name='submit_review'),
    path('doctors/<int:doctor_id>/reviews/', views.doctor_reviews_partial, name='doctor_reviews'),

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

    # Doctor URLs - Analytics
    path('analytics/', views.doctor_analytics_view, name='doctor_analytics'),

    # Doctor URLs - Prescriptions
    path('appointments/<int:appointment_id>/prescription/write/', views.doctor_write_prescription, name='write_prescription'),

    # Feature 3: Doctor Time-Off
    path('availability/time-off/', views.doctor_time_off_list, name='time_off_list'),
    path('availability/time-off/<int:block_id>/delete/', views.doctor_delete_time_off, name='delete_time_off'),

    # Feature 4: Waitlist
    path('doctors/<int:doctor_id>/waitlist/join/', views.patient_join_waitlist, name='join_waitlist'),
    path('doctors/<int:doctor_id>/waitlist/leave/', views.patient_leave_waitlist, name='leave_waitlist'),

    # Feature 5: Health Records
    path('health-records/', views.patient_health_records, name='patient_health_records'),
    path('health-records/<int:record_id>/delete/', views.patient_delete_health_record, name='delete_health_record'),
    path('health-records/<int:record_id>/share/', views.patient_share_health_record, name='share_health_record'),
    path('patient/<int:patient_id>/records/', views.doctor_view_shared_records, name='doctor_view_patient_records'),

    # Feature 6: Follow-Up
    path('appointments/<int:appointment_id>/followup/', views.doctor_schedule_followup, name='schedule_followup'),

    # Feature 7: Medical History
    path('patients/<int:patient_id>/history/', views.doctor_patient_history, name='patient_history'),

    # Feature 9: Referrals
    path('appointments/<int:appointment_id>/referral/', views.doctor_create_referral, name='create_referral'),
    path('referrals/', views.patient_referrals_list, name='patient_referrals'),

    # Billing download
    path('appointments/<int:appointment_id>/billing/', views.patient_billing_download, name='billing_download'),

    # Availability exceptions
    path('availability/exceptions/create/', views.doctor_exception_create, name='create_exception'),
    path('availability/exceptions/<int:exception_id>/delete/', views.doctor_exception_delete, name='delete_exception'),

    # Review responses
    path('reviews/<int:review_id>/respond/', views.doctor_respond_to_review, name='respond_to_review'),
]
