from django.urls import path
from . import views

urlpatterns = [
    # Landing page
    path('', views.landing_page, name='landing'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Signup - Role selection
    path('signup/', views.signup_role_select, name='signup'),

    # Patient signup wizard
    path('signup/patient/', views.patient_signup_wizard, {'step': 1}, name='patient_signup_start'),
    path('signup/patient/<int:step>/', views.patient_signup_wizard, name='patient_signup'),

    # Doctor signup wizard
    path('signup/doctor/', views.doctor_signup_wizard, {'step': 1}, name='doctor_signup_start'),
    path('signup/doctor/<int:step>/', views.doctor_signup_wizard, name='doctor_signup'),

    # Email verification
    path('verify-email/<str:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),

    # Password reset
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<str:token>/', views.reset_password, name='reset_password'),

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('profile/upload-image/', views.upload_profile_image, name='upload_profile_image'),
    path('profile/remove-image/', views.remove_profile_image, name='remove_profile_image'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/theme/', views.update_theme, name='update_theme'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
