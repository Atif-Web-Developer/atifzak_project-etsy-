"""Small helpers shared by views, signals and other apps."""
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import ActivityLog, Notification


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_activity(request, action, description='', user=None):
    if user is None and request is not None and request.user.is_authenticated:
        user = request.user
    return ActivityLog.objects.create(
        user=user,
        action=action,
        description=description[:255],
        ip_address=client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT', '')[:255] if request else ''),
    )


def notify(recipient, title, message='', level='info', icon='ri-notification-3-line', link=''):
    return Notification.objects.create(
        recipient=recipient, title=title, message=message, level=level, icon=icon, link=link,
    )


def notify_admins(title, message='', level='info', icon='ri-notification-3-line', link='', exclude=None):
    """Notify every active user who is allowed to manage users."""
    User = get_user_model()
    admins = User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(role__can_manage_users=True))
    if exclude is not None:
        admins = admins.exclude(pk=exclude.pk)
    Notification.objects.bulk_create([
        Notification(recipient=u, title=title, message=message, level=level, icon=icon, link=link)
        for u in admins
    ])
