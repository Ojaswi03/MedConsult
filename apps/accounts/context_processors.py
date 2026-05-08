"""
Context processors for accounts app - provide user info to all templates.
"""


def user_info(request):
    """Provide user display info and org context to all templates."""
    if request.user.is_authenticated:
        unread_count = request.user.notifications.filter(is_read=False).count()
        try:
            from apps.messaging.selectors import get_total_unread_count
            unread_messages = get_total_unread_count(request.user)
        except Exception:
            unread_messages = 0

        from apps.accounts.permissions import is_platform_staff
        _is_platform_staff = is_platform_staff(request.user)
        try:
            from apps.accounts.org_context import get_selected_organization
            org_ctx = get_selected_organization(request)
            user_organization = org_ctx.organization
            user_membership = org_ctx.membership
        except Exception:
            user_organization = None
            user_membership = None

        active_organizations = []
        if _is_platform_staff:
            try:
                from apps.accounts.models import Organization
                active_organizations = list(
                    Organization.objects.filter(status='active').order_by('name')
                )
            except Exception:
                pass

        return {
            'user_display_name': request.user.get_display_name(),
            'user_initials': request.user.get_initials(),
            'user_role': request.user.role,
            'unread_notifications_count': unread_count,
            'unread_message_count': unread_messages,
            'is_platform_staff': _is_platform_staff,
            'user_organization': user_organization,
            'user_membership': user_membership,
            'active_organizations': active_organizations,
        }
    return {}
