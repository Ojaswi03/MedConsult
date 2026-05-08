import secrets
from django.db import transaction
from apps.accounts.models import Organization, OrganizationInvite


@transaction.atomic
def create_and_send_invite(org: Organization, invited_by, email: str, role: str) -> OrganizationInvite:
    """Create an OrganizationInvite and send an invitation email."""
    # Revoke any existing pending invite for this email+org combo
    OrganizationInvite.objects.filter(
        organization=org, email=email.lower(), status='pending',
    ).update(status='revoked')

    raw_token = secrets.token_urlsafe(32)
    invite = OrganizationInvite.objects.create(
        organization=org,
        invited_by=invited_by,
        email=email.lower(),
        role=role,
        token_hash=OrganizationInvite.make_token_hash(raw_token),
    )

    _send_invite_email(invite, raw_token)
    return invite


def _send_invite_email(invite: OrganizationInvite, raw_token: str) -> None:
    from django.core.mail import send_mail
    from django.conf import settings
    from django.urls import reverse

    accept_url = f"{getattr(settings, 'BASE_URL', 'http://localhost:8000')}{reverse('organizations:accept_invite', kwargs={'token': raw_token})}"

    try:
        send_mail(
            subject=f"You're invited to join {invite.organization.name} on MedConsult",
            message=(
                f"Hi,\n\n"
                f"{invite.invited_by.get_display_name()} has invited you to join "
                f"{invite.organization.name} as {invite.get_role_display()}.\n\n"
                f"Accept your invitation here:\n{accept_url}\n\n"
                f"This link expires in 7 days.\n\n"
                f"If you did not expect this invitation, you can ignore this email.\n\n"
                f"— MedConsult Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invite.email],
            fail_silently=True,
        )
    except Exception:
        pass
