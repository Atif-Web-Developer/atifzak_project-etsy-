from .modules import grouped_modules, module_for_view


def navigation(request):
    """Sidebar menu and topbar notifications for every signed-in page."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    current_module = None
    match = getattr(request, 'resolver_match', None)
    if match:
        func = getattr(match.func, 'view_class', match.func)
        current_module = module_for_view(func.__module__.split('.')[0], match.url_name)

    notifications = user.notifications.all()
    return {
        'nav_groups': grouped_modules(user.accessible_modules),
        'nav_current_module': current_module,
        'nav_current_url': match.view_name if match else '',
        'nav_notifications': notifications[:6],
        'nav_unread_count': notifications.filter(is_read=False).count(),
    }
