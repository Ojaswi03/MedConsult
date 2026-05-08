from django.shortcuts import render


def org_register(request):
    return render(request, 'organizations/register.html')


def accept_invite(request, token):
    return render(request, 'organizations/accept_invite.html')


def org_dashboard(request, org_slug):
    return render(request, 'organizations/dashboard.html')


def org_settings(request, org_slug):
    return render(request, 'organizations/settings.html')


def staff_list(request, org_slug):
    return render(request, 'organizations/staff_list.html')


def send_invite(request, org_slug):
    return render(request, 'organizations/send_invite.html')


def deactivate_member(request, org_slug, member_id):
    return render(request, 'organizations/deactivate_member.html')
