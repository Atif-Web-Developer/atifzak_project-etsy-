from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, ProfileForm, RoleForm, StyledFormMixin, UserForm
from .models import ActivityLog, Notification, Role
from .modules import MODULES, MODULE_MAP
from .services import client_ip, log_activity, notify, notify_admins

User = get_user_model()

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60


def _safe_next(request, fallback):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return nxt
    return fallback


def requires(flag):
    """Restrict a view to users whose role grants `flag` (e.g. 'can_manage_users')."""
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not getattr(request.user, flag, False):
                raise PermissionDenied('You do not have permission to open this page.')
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


# =====================================================================
# Authentication
# =====================================================================

class LoginView(auth_views.LoginView):
    template_name = 'accounts/auth/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def _lock_key(self):
        username = (self.request.POST.get('username') or '').strip().lower()
        return f'login-fail:{client_ip(self.request)}:{username}'

    def post(self, request, *args, **kwargs):
        if cache.get(self._lock_key(), 0) >= MAX_LOGIN_ATTEMPTS:
            form = self.authentication_form(request, initial={'username': request.POST.get('username', '')})
            return self.render_to_response(self.get_context_data(
                form=form, lockout_error='Too many failed attempts. Please wait 15 minutes and try again.'))
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._lock_key()
        cache.set(key, cache.get(key, 0) + 1, LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._lock_key())
        response = super().form_valid(form)
        if not form.cleaned_data.get('remember_me'):
            self.request.session.set_expiry(0)  # expire when the browser closes
        messages.success(self.request, f'Welcome back, {self.request.user.display_name}!')
        return response


def logout_view(request):
    # Only POST signs out, so a link on another site cannot log users out.
    if request.method != 'POST':
        return redirect('overview' if request.user.is_authenticated else 'login')
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, 'You have been signed out.')
    return redirect('login')


class PasswordResetView(auth_views.PasswordResetView):
    template_name = 'accounts/auth/password_reset.html'
    email_template_name = 'accounts/auth/emails/password_reset.txt'
    subject_template_name = 'accounts/auth/emails/password_reset_subject.txt'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter your email'})
        return form


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'accounts/auth/password_reset_confirm.html'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for f in form.fields.values():
            f.widget.attrs['class'] = 'form-control'
        return form

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(self.request, 'password_reset', 'Password reset via email link', user=form.user)
        notify(form.user, 'Password was reset', 'Your password was reset using the email link.',
               level='warning', icon='ri-lock-unlock-line')
        return response


# =====================================================================
# Profile
# =====================================================================

class StyledPasswordChangeForm(StyledFormMixin, PasswordChangeForm):
    pass


def profile_view(request):
    user = request.user
    profile_form = ProfileForm(instance=user)
    password_form = StyledPasswordChangeForm(user)
    active_tab = request.GET.get('tab', 'overview')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            active_tab = 'edit'
            profile_form = ProfileForm(request.POST, request.FILES, instance=user)
            if profile_form.is_valid():
                if request.POST.get('remove_avatar') and user.avatar:
                    user.avatar.delete(save=False)
                profile_form.save()
                log_activity(request, 'profile_update', 'Updated profile details')
                messages.success(request, 'Your profile has been updated.')
                return redirect(f"{reverse('accounts:profile')}?tab=edit")
        elif action == 'password':
            active_tab = 'security'
            password_form = StyledPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                log_activity(request, 'password_change', 'Changed account password')
                notify(user, 'Password changed', 'Your account password was changed successfully.',
                       level='success', icon='ri-lock-password-line')
                messages.success(request, 'Your password has been changed.')
                return redirect(f"{reverse('accounts:profile')}?tab=security")

    modules = [m for m in MODULES if user.has_module(m.key)]
    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'modules': modules,
        'recent_activity': user.activity.all()[:8],
    })


# =====================================================================
# Notifications
# =====================================================================

def notification_list(request):
    qs = request.user.notifications.all()
    status = request.GET.get('status', 'all')
    if status == 'unread':
        qs = qs.filter(is_read=False)
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    return render(request, 'accounts/notifications.html', {'page': page, 'status': status})


def notification_open(request, pk):
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=['is_read'])
    if note.link and url_has_allowed_host_and_scheme(note.link, allowed_hosts={request.get_host()}):
        return redirect(note.link)
    return redirect('accounts:notifications')


@require_POST
def notification_mark_all(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect(_safe_next(request, 'accounts:notifications'))


@require_POST
def notification_delete(request, pk):
    get_object_or_404(Notification, pk=pk, recipient=request.user).delete()
    messages.success(request, 'Notification removed.')
    return redirect('accounts:notifications')


@require_POST
def notification_clear(request):
    request.user.notifications.filter(is_read=True).delete()
    messages.success(request, 'Read notifications cleared.')
    return redirect('accounts:notifications')


# =====================================================================
# User management
# =====================================================================

def _role_hints():
    """Role summaries shown next to the role picker on the user form."""
    return {
        str(r.pk): {
            'name': r.name,
            'description': r.description,
            'modules': [MODULE_MAP[k].label for k in r.modules if k in MODULE_MAP],
        }
        for r in Role.objects.all()
    }


def _guard_target(request, target):
    """Only superusers may modify superuser accounts."""
    if target.is_superuser and not request.user.is_superuser:
        raise PermissionDenied('Only a super admin can modify this account.')


@requires('can_manage_users')
def user_list(request):
    qs = User.objects.select_related('role').order_by('-date_joined')
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) |
                       Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if role:
        qs = qs.filter(role__slug=role)
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)

    all_users = User.objects.all()
    stats = {
        'total': all_users.count(),
        'active': all_users.filter(is_active=True).count(),
        'inactive': all_users.filter(is_active=False).count(),
        'no_role': all_users.filter(role__isnull=True).count(),
    }
    return render(request, 'accounts/users/list.html', {
        'page': Paginator(qs, 12).get_page(request.GET.get('page')),
        'roles': Role.objects.all(),
        'filters': {'q': q, 'role': role, 'status': status},
        'stats': stats,
    })


@requires('can_manage_users')
def user_create(request):
    form = UserForm(request.POST or None, acting_user=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        log_activity(request, 'user_create', f'Created user {user.username} ({user.role_label})')
        notify(user, 'Welcome aboard!', f'Your account was created with the {user.role_label} role.',
               level='success', icon='ri-hand-heart-line', link=reverse('accounts:profile'))
        notify_admins('New user created', f'{request.user.display_name} added {user.display_name} as {user.role_label}.',
                      icon='ri-user-add-line', link=reverse('accounts:user_edit', args=[user.pk]),
                      exclude=request.user)
        messages.success(request, f'User “{user.username}” was created.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/users/form.html', {'form': form, 'is_new': True, 'role_hints': _role_hints()})


@requires('can_manage_users')
def user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_target(request, target)
    old_role = target.role
    form = UserForm(request.POST or None, instance=target, acting_user=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        log_activity(request, 'user_update', f'Updated user {user.username}')
        if user.role != old_role:
            notify(user, 'Your role changed', f'You now have the {user.role_label} role.',
                   level='info', icon='ri-shield-user-line', link=reverse('accounts:profile'))
        if form.cleaned_data.get('password1') and user != request.user:
            notify(user, 'Password updated by an administrator', 'Use your new password next time you sign in.',
                   level='warning', icon='ri-lock-password-line')
        if user == request.user and form.cleaned_data.get('password1'):
            update_session_auth_hash(request, user)
        messages.success(request, f'User “{user.username}” was updated.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/users/form.html', {
        'form': form, 'is_new': False, 'target': target, 'role_hints': _role_hints(),
        'target_activity': target.activity.all()[:6],
    })


@requires('can_manage_users')
@require_POST
def user_toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_target(request, target)
    if target == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
    else:
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        state = 'activated' if target.is_active else 'deactivated'
        log_activity(request, 'user_update', f'{state.title()} user {target.username}')
        messages.success(request, f'User “{target.username}” was {state}.')
    return redirect(_safe_next(request, 'accounts:user_list'))


@requires('can_manage_users')
@require_POST
def user_delete(request, pk):
    target = get_object_or_404(User, pk=pk)
    _guard_target(request, target)
    if target == request.user:
        messages.error(request, 'You cannot delete your own account.')
    else:
        username = target.username
        target.delete()
        log_activity(request, 'user_delete', f'Deleted user {username}')
        messages.success(request, f'User “{username}” was deleted.')
    return redirect('accounts:user_list')


# =====================================================================
# Roles
# =====================================================================

@requires('can_manage_roles')
def role_list(request):
    roles = Role.objects.annotate(user_count=Count('users')).order_by('name')
    return render(request, 'accounts/roles/list.html', {
        'roles': roles,
        'module_map': MODULE_MAP,
        'module_total': len(MODULES),
    })


def _role_form_view(request, role=None):
    form = RoleForm(request.POST or None, instance=role)
    if request.method == 'POST' and form.is_valid():
        is_new = role is None
        role = form.save()
        log_activity(request, 'role_create' if is_new else 'role_update',
                     f"{'Created' if is_new else 'Updated'} role {role.name}")
        if not is_new:
            for member in role.users.exclude(pk=request.user.pk):
                notify(member, 'Your permissions changed',
                       f'The {role.name} role was updated by an administrator.',
                       icon='ri-shield-check-line', link=reverse('accounts:profile'))
        messages.success(request, f'Role “{role.name}” was {"created" if is_new else "saved"}.')
        return redirect('accounts:role_list')

    groups = {}
    for m in MODULES:
        groups.setdefault(m.group, []).append(m)
    selected = set(form['modules'].value() or [])
    return render(request, 'accounts/roles/form.html', {
        'form': form, 'role': role, 'module_groups': groups.items(), 'selected': selected,
    })


@requires('can_manage_roles')
def role_create(request):
    return _role_form_view(request)


@requires('can_manage_roles')
def role_edit(request, pk):
    return _role_form_view(request, get_object_or_404(Role, pk=pk))


@requires('can_manage_roles')
@require_POST
def role_delete(request, pk):
    role = get_object_or_404(Role, pk=pk)
    if role.is_system:
        messages.error(request, f'“{role.name}” is a system role and cannot be deleted.')
    else:
        affected = role.users.count()
        name = role.name
        role.delete()
        log_activity(request, 'role_delete', f'Deleted role {name}')
        note = f' {affected} user(s) now have no role.' if affected else ''
        messages.success(request, f'Role “{name}” was deleted.{note}')
    return redirect('accounts:role_list')


# =====================================================================
# Activity log
# =====================================================================

@requires('can_view_activity')
def activity_list(request):
    qs = ActivityLog.objects.select_related('user')
    action = request.GET.get('action', '')
    user_id = request.GET.get('user', '')
    if action:
        qs = qs.filter(action=action)
    if user_id.isdigit():
        qs = qs.filter(user_id=user_id)
    return render(request, 'accounts/activity.html', {
        'page': Paginator(qs, 25).get_page(request.GET.get('page')),
        'actions': ActivityLog.ACTION_CHOICES,
        'users': User.objects.order_by('username'),
        'filters': {'action': action, 'user': user_id},
    })


# =====================================================================
# Error pages
# =====================================================================

def permission_denied(request, exception=None):
    return render(request, '403.html', {'reason': str(exception or '')}, status=403)


def page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def server_error(request):
    # Rendered without the request so context processors (DB queries) can't fail a second time.
    return HttpResponseServerError(render_to_string('500.html'))
