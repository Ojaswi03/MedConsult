"""
Context processors for accounts app - provide user info to all templates.
"""


def user_info(request):
    """Provide user display info to all templates."""
    if request.user.is_authenticated:
        return {
            'user_display_name': request.user.get_display_name(),
            'user_initials': request.user.get_initials(),
            'user_role': request.user.role,
        }
    return {}
