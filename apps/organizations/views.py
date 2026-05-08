from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from apps.accounts.permissions import is_platform_staff, can_manage_staff, can_invite_staff
from apps.accounts.org_context import get_selected_organization


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
    from django.core.exceptions import PermissionDenied

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        from django.http import Http404
        raise Http404

    if not is_platform_staff(request.user):
        from apps.accounts.models import OrganizationMembership
        if not OrganizationMembership.objects.filter(
            user=request.user, organization=org, is_active=True,
        ).exists():
            raise PermissionDenied

    from apps.adminpanel.selectors import get_org_appointments, get_org_staff_members
    recent_appointments = get_org_appointments(org, user=request.user)[:10]
    staff = get_org_staff_members(org)

    return render(request, 'organizations/dashboard.html', {
        'org': org,
        'recent_appointments': recent_appointments,
        'staff': staff,
    })


@login_required
def org_settings(request, org_slug):
    from apps.accounts.models import Organization
    from django.core.exceptions import PermissionDenied
    from django.http import Http404

    try:
        org = Organization.objects.get(slug=org_slug)
    except Organization.DoesNotExist:
        raise Http404

    if not can_manage_staff(request.user, org):
        raise PermissionDenied

    return render(request, 'organizations/settings.html', {'org': org})


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
