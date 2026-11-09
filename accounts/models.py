from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .modules import ALL_MODULE_KEYS


class Role(models.Model):
    """A named set of permissions assigned to users."""

    COLOR_CHOICES = [
        ('primary', 'Green'),
        ('info', 'Blue'),
        ('secondary', 'Indigo'),
        ('warning', 'Amber'),
        ('danger', 'Red'),
        ('dark', 'Dark'),
    ]

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=20, choices=COLOR_CHOICES, default='primary')
    modules = models.JSONField(default=list, blank=True, help_text='Module keys this role can access.')
    can_manage_users = models.BooleanField(default=False)
    can_manage_roles = models.BooleanField(default=False)
    can_view_activity = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False, help_text='System roles cannot be deleted.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Drop keys for modules that no longer exist.
        self.modules = [k for k in self.modules if k in ALL_MODULE_KEYS]
        super().save(*args, **kwargs)

    @property
    def module_count(self):
        return len(self.modules)


class Notification(models.Model):
    LEVEL_CHOICES = [
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Alert'),
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    icon = models.CharField(max_length=50, default='ri-notification-3-line')
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'])]

    def __str__(self):
        return f'{self.title} → {self.recipient}'

    def get_absolute_url(self):
        return reverse('accounts:notification_open', args=[self.pk])


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('login', 'Signed in'),
        ('logout', 'Signed out'),
        ('login_failed', 'Failed sign-in'),
        ('password_change', 'Changed password'),
        ('password_reset', 'Reset password'),
        ('profile_update', 'Updated profile'),
        ('user_create', 'Created user'),
        ('user_update', 'Updated user'),
        ('user_delete', 'Deleted user'),
        ('role_create', 'Created role'),
        ('role_update', 'Updated role'),
        ('role_delete', 'Deleted role'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='activity')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_action_display()} – {self.user or "unknown"}'

    @property
    def icon(self):
        return {
            'login': ('ri-login-circle-line', 'success'),
            'logout': ('ri-logout-circle-line', 'secondary'),
            'login_failed': ('ri-error-warning-line', 'danger'),
            'password_change': ('ri-lock-password-line', 'warning'),
            'password_reset': ('ri-lock-unlock-line', 'warning'),
            'profile_update': ('ri-user-settings-line', 'info'),
            'user_create': ('ri-user-add-line', 'primary'),
            'user_update': ('ri-user-follow-line', 'info'),
            'user_delete': ('ri-user-unfollow-line', 'danger'),
            'role_create': ('ri-shield-user-line', 'primary'),
            'role_update': ('ri-shield-check-line', 'info'),
            'role_delete': ('ri-shield-cross-line', 'danger'),
        }.get(self.action, ('ri-information-line', 'secondary'))
