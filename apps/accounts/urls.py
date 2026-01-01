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

    # Profile
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.settings_view, name='settings'),
]
