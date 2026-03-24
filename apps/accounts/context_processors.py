"""
Context processors for accounts app - provide user info to all templates.
"""


def user_info(request):
    """Provide user display info to all templates."""
    if request.user.is_authenticated:
        unread_count = request.user.notifications.filter(is_read=False).count()
        try:
            from apps.messaging.selectors import get_total_unread_count
            unread_messages = get_total_unread_count(request.user)
        except Exception:
            unread_messages = 0
        return {
            'user_display_name': request.user.get_display_name(),
            'user_initials': request.user.get_initials(),
            'user_role': request.user.role,
            'unread_notifications_count': unread_count,
            'unread_message_count': unread_messages,
        }
    return {}
