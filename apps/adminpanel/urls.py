from django.urls import path
from . import views

app_name = 'adminpanel'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    path('charts/', views.dashboard_charts_data, name='dashboard_charts'),

    # Users
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/export/', views.users_export, name='users_export'),

    # Doctors
    path('doctors/', views.doctors_list, name='doctors_list'),
    path('doctors/<int:doctor_id>/', views.doctor_detail, name='doctor_detail'),
    path('doctors/<int:doctor_id>/document/<str:doc_type>/', views.doctor_document_view, name='doctor_document'),

    # Doctor Slot Management (Admin)
    path('doctors/<int:doctor_id>/manage/', views.admin_doctor_manage, name='doctor_manage'),
    path('doctors/<int:doctor_id>/calendar/', views.admin_doctor_calendar, name='doctor_calendar'),
    path('doctors/<int:doctor_id>/slots/create/', views.admin_create_slot, name='create_slot'),
    path('slots/<int:slot_id>/block/', views.admin_block_slot, name='block_slot'),
    path('slots/<int:slot_id>/unblock/', views.admin_unblock_slot, name='unblock_slot'),
    path('slots/<int:slot_id>/delete/', views.admin_delete_slot, name='delete_slot'),

    # Patient Management (Admin)
    path('patients/<int:patient_id>/manage/', views.admin_patient_manage, name='patient_manage'),
    path('appointments/<int:appointment_id>/cancel/', views.admin_cancel_appointment, name='cancel_appointment'),

    # Verification
    path('verify/', views.doctor_verification_queue, name='verification_queue'),
    path('verify/<int:doctor_id>/approve/', views.verify_doctor, name='verify_doctor'),
    path('verify/<int:doctor_id>/reject/', views.reject_doctor, name='reject_doctor'),

    # Appointments
    path('appointments/', views.appointments_list, name='appointments_list'),
    path('appointments/export/', views.appointments_export, name='appointments_export'),

    # Financial
    path('financial/', views.financial_overview, name='financial_overview'),

    # Audit
    path('audit/', views.audit_logs, name='audit_logs'),

    # Bulk operations
    path('verify/bulk-verify/', views.bulk_verify_doctors_view, name='bulk_verify'),
    path('verify/bulk-reject/', views.bulk_reject_doctors_view, name='bulk_reject'),

    # New admin pages
    path('waitlist/', views.waitlist_overview, name='waitlist_overview'),
    path('referrals/', views.referral_tracking, name='referral_tracking'),
    path('health-records/logs/', views.health_record_logs, name='health_record_logs'),
    path('financial/insurance/', views.insurance_breakdown, name='insurance_breakdown'),
    path('appointments/<int:appointment_id>/refund/', views.admin_refund_appointment, name='refund_appointment'),

    # Organization review
    path('organizations/', views.organization_list, name='organization_list'),
    path('organizations/<int:org_id>/', views.organization_detail, name='organization_detail'),
    path('organizations/<int:org_id>/approve/', views.organization_approve, name='organization_approve'),
    path('organizations/<int:org_id>/reject/', views.organization_reject, name='organization_reject'),
    path('organizations/<int:org_id>/suspend/', views.organization_suspend, name='organization_suspend'),
    path('organizations/<int:org_id>/reactivate/', views.organization_reactivate, name='organization_reactivate'),
    path('organizations/<int:org_id>/needs-info/', views.organization_needs_info, name='organization_needs_info'),
]
