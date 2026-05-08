from django.urls import path
from . import views

urlpatterns = [
    # Doctor browsing and slot viewing
    path('doctors/', views.patient_doctors_list, name='patient_doctors_list'),
    path('doctors/<int:doctor_id>/', views.patient_doctor_detail, name='doctor_detail'),
    path('doctors/<int:doctor_id>/slots/', views.patient_slots_updates, name='patient_slots_updates'),
    path('doctors/<int:doctor_id>/reviews/', views.doctor_reviews_partial, name='doctor_reviews'),
    path('doctors/<int:doctor_id>/waitlist/join/', views.patient_join_waitlist, name='join_waitlist'),
    path('doctors/<int:doctor_id>/waitlist/leave/', views.patient_leave_waitlist, name='leave_waitlist'),

    # Booking
    path('book/<int:slot_id>/', views.patient_book_appointment, name='book_appointment'),

    # Appointments
    path('appointments/', views.patient_appointments_list, name='patient_appointments'),
    path('appointments/<int:appointment_id>/cancel/', views.patient_cancel_appointment, name='cancel_appointment'),
    path('appointments/<int:appointment_id>/reschedule/', views.patient_reschedule_appointment, name='reschedule_appointment'),
    path('appointments/<int:appointment_id>/prescription/download/', views.patient_download_prescription, name='download_prescription'),
    path('appointments/<int:appointment_id>/billing/', views.patient_billing_download, name='billing_download'),

    # Symptom selector (HTMX partials)
    path('symptoms/body-parts/', views.get_body_parts, name='get_body_parts'),
    path('symptoms/body-parts/<int:body_part_id>/conditions/', views.get_conditions, name='get_conditions'),
    path('symptoms/list/', views.get_symptoms, name='get_symptoms'),

    # Reviews
    path('reviews/', views.patient_reviews_list, name='patient_reviews'),
    path('reviews/<int:appointment_id>/submit/', views.patient_submit_review, name='submit_review'),

    # Health records
    path('health-records/', views.patient_health_records, name='patient_health_records'),
    path('health-records/<int:record_id>/download/', views.health_record_download, name='health_record_download'),
    path('health-records/<int:record_id>/delete/', views.patient_delete_health_record, name='delete_health_record'),
    path('health-records/<int:record_id>/share/', views.patient_share_health_record, name='share_health_record'),

    # Referrals
    path('referrals/', views.patient_referrals_list, name='patient_referrals'),

    # HIPAA data export
    path('export/', views.patient_data_export, name='patient_data_export'),
]
