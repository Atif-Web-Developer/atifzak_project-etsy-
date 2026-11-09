from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .modules import module_for_view

# URL names reachable without signing in.
PUBLIC_URL_NAMES = {
    'login',
    'password_reset', 'password_reset_done', 'password_reset_confirm', 'password_reset_complete',
}
# Path prefixes handled by something else (Django admin has its own login, static/media are files).
EXEMPT_PREFIXES = ('/admin/', '/static/', '/media/', '/favicon.ico')


class AccessControlMiddleware:
    """
    Enforces authentication site-wide and role-based module access.

    * Anonymous users are sent to the login page for every non-public view.
    * Signed-in users may only open views that belong to a module their role grants
      (see accounts.modules). Views outside any module (profile, notifications …) are open
      to every signed-in user; administration views check their own permissions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.path.startswith(EXEMPT_PREFIXES):
            return None

        match = request.resolver_match
        url_name = match.url_name if match else None
        if url_name in PUBLIC_URL_NAMES:
            return None

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

        func = getattr(view_func, 'view_class', view_func)
        app_label = func.__module__.split('.')[0]
        module_key = module_for_view(app_label, url_name)
        if module_key and not request.user.has_module(module_key):
            raise PermissionDenied(f'Your role does not include access to this module.')
        return None
