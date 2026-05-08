from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden

from apps.accounts.permissions import (
    is_platform_staff, can_manage_staff, can_invite_staff, get_membership,
)
from apps.accounts.org_context import get_selected_organization


DASHBOARD_TEMPLATES = {
    'hospital_owner': 'organizations/dashboard_owner.html',
    'hospital_admin': 'organizations/dashboard_admin.html',
    'scheduler': 'organizations/dashboard_scheduler.html',
    'platform_owner': 'organizations/dashboard_owner.html',
    'platform_admin': 'organizations/dashboard_owner.html',
}


def org_register(request):
    from .forms import OrgOwnerAccountForm, OrgProfileForm
    from .services import register_organization

    account_form = OrgOwnerAccountForm(request.POST or None)
    org_form = OrgProfileForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if account_form.is_valid() and org_form.is_valid():
            register_organization(account_form.cleaned_data, org_form.cleaned_data)
            return redirect(reverse('organizations:org_register_pending'))

    return render(request, 'organizations/register.html', {
        'account_form': account_form,
        'org_form': org_form,
    })


def org_register_pending(request):
    return render(request, 'organizations/register_pending.html')


@login_required
def accept_invite(request, token):
    from apps.accounts.models import OrganizationInvite
    from django.utils import timezone

    try:
        invite = OrganizationInvite.objects.select_related('organization').get(
            token_hash=OrganizationInvite.make_token_hash(token),
            status='pending',
        )
    except OrganizationInvite.DoesNotExist:
        return render(request, 'organizations/invite_invalid.html', status=404)

    if invite.expires_at < timezone.now():
        invite.status = 'expired'
        invite.save(update_fields=['status'])
        return render(request, 'organizations/invite_invalid.html', {'reason': 'expired'})

    if request.method == 'POST':
        from apps.accounts.models import OrganizationMembership
        from django.db import IntegrityError
        try:
            OrganizationMembership.objects.create(
                user=request.user,
                organization=invite.organization,
                role=invite.role,
                is_active=True,
            )
        except IntegrityError:
            # Already a member — update role
            OrganizationMembership.objects.filter(
                user=request.user, organization=invite.organization,
            ).update(role=invite.role, is_active=True)

        invite.status = 'accepted'
        invite.accepted_by = request.user
        invite.save(update_fields=['status', 'accepted_by'])

        return redirect(reverse('organizations:org_dashboard', kwargs={'org_slug': invite.organization.slug}))

    return render(request, 'organizations/accept_invite.html', {'invite': invite})


@login_required
def org_dashboard(request, org_slug):
    from apps.accounts.models import Organization
    from apps.accounts.models import OrganizationInvite, OrganizationMembership
    from apps.scheduling.models import Appointment, Slot
    from apps.accounts.models import DoctorProfile
    from django.core.exceptions import PermissionDenied
    from django.utils import timezone

    org = get_object_or_404(Organization, slug=org_slug)
    if org.status not in ('active', 'pending') and not is_platform_staff(request.user):
        return HttpResponseForbidden("This organization is not active.")

    if is_platform_staff(request.user):
        membership_role = request.user.role
    else:
        membership = get_membership(request.user, org)
        if not membership or not membership.is_active:
            raise PermissionDenied
        membership_role = membership.role

    template = DASHBOARD_TEMPLATES.get(membership_role, 'organizations/dashboard_deferred.html')
    today = timezone.now().date()

    ctx = {
        'org': org,
        'membership_role': membership_role,
        'active_doctors': DoctorProfile.objects.filter(
            organization=org, user__is_active=True,
        ).count(),
        'today_appointments': Appointment.objects.filter(
            organization=org, slot__start_datetime__date=today,
        ).count(),
        'pending_invites': OrganizationInvite.objects.filter(
            organization=org, status='pending',
        ).count(),
        'staff_count': OrganizationMembership.objects.filter(
            organization=org, is_active=True,
        ).count(),
    }
    return render(request, template, ctx)


@login_required
@login_required
def org_settings(request, org_slug):
    from apps.accounts.models import Organization
    from django.core.exceptions import PermissionDenied
    from django.contrib import messages as django_messages

    org = get_object_or_404(Organization, slug=org_slug)

    if not (is_platform_staff(request.user) or
            get_membership(request.user, org) and
            get_membership(request.user, org).role in ('hospital_owner', 'hospital_admin')):
        raise PermissionDenied

    from .forms import OrgEditForm
    initial = {
        'name': org.name, 'org_type': org.org_type,
        'address': org.address, 'phone': org.phone, 'website': org.website,
    }
    form = OrgEditForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        org.name = form.cleaned_data['name']
        org.org_type = form.cleaned_data['org_type']
        org.address = form.cleaned_data.get('address', '')
        org.phone = form.cleaned_data.get('phone', '')
        org.website = form.cleaned_data.get('website', '')
        if form.cleaned_data.get('logo'):
            org.logo = form.cleaned_data['logo']
        org.save()
        django_messages.success(request, "Organization profile updated.")
        return redirect(reverse('organizations:org_settings', kwargs={'org_slug': org.slug}))

    return render(request, 'organizations/settings.html', {'org': org, 'form': form})


@login_required
def staff_list(request, org_slug):
    from apps.accounts.models import Organization
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    if not can_manage_staff(request.user, org):
        raise PermissionDenied

    from apps.adminpanel.selectors import get_org_staff_members
    members = get_org_staff_members(org)
    from apps.accounts.permissions import get_invitable_roles
    invitable_roles = get_invitable_roles(request.user, org)

    return render(request, 'organizations/staff_list.html', {
        'org': org,
        'members': members,
        'invitable_roles': invitable_roles,
    })


@login_required
def send_invite(request, org_slug):
    from apps.accounts.models import Organization
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    if not can_invite_staff(request.user, org):
        raise PermissionDenied

    from apps.accounts.permissions import get_invitable_roles
    invitable_roles = get_invitable_roles(request.user, org)

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        role = request.POST.get('role', '')
        if not email or role not in invitable_roles:
            return render(request, 'organizations/send_invite.html', {
                'org': org,
                'invitable_roles': invitable_roles,
                'error': 'Invalid email or role.',
            })

        from apps.organizations.invite_service import create_and_send_invite
        create_and_send_invite(org=org, invited_by=request.user, email=email, role=role)
        return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))

    return render(request, 'organizations/send_invite.html', {
        'org': org,
        'invitable_roles': invitable_roles,
    })


@login_required
@require_POST
def deactivate_member(request, org_slug, member_id):
    from apps.accounts.models import Organization, OrganizationMembership
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    if not can_manage_staff(request.user, org):
        raise PermissionDenied

    OrganizationMembership.objects.filter(
        id=member_id, organization=org,
    ).update(is_active=False)

    return redirect(reverse('organizations:staff_list', kwargs={'org_slug': org_slug}))
