from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .services import log_activity


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_activity(request, 'login', 'Signed in', user=user)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_activity(request, 'logout', 'Signed out', user=user)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    log_activity(request, 'login_failed', f"Failed sign-in for “{credentials.get('username', '')}”")
