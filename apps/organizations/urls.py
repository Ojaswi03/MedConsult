from django.urls import path
from . import views

app_name = 'organizations'

urlpatterns = [
    path('register/', views.org_register, name='org_register'),
    path('register/pending/', views.org_register_pending, name='org_register_pending'),
    path('invite/<str:token>/', views.accept_invite, name='accept_invite'),
    path('<slug:org_slug>/', views.org_dashboard, name='org_dashboard'),
    path('<slug:org_slug>/settings/', views.org_settings, name='org_settings'),
    path('<slug:org_slug>/staff/', views.staff_list, name='staff_list'),
    path('<slug:org_slug>/staff/invite/', views.send_invite, name='send_invite'),
    path('<slug:org_slug>/staff/<int:member_id>/deactivate/', views.deactivate_member, name='deactivate_member'),
]
