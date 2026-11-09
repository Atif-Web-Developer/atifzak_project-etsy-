from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    """Custom user model for future scaling (e.g., Premium features)."""
    is_premium = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    role = models.ForeignKey('accounts.Role', on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=100, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    # ----------------------------------------------------------- Permissions
    # Superusers bypass role checks entirely; everyone else is limited by their role.

    @property
    def accessible_modules(self):
        from accounts.modules import ALL_MODULE_KEYS
        if self.is_superuser:
            return set(ALL_MODULE_KEYS)
        return set(self.role.modules) if self.role_id else set()

    def has_module(self, key):
        return key in self.accessible_modules

    @property
    def can_manage_users(self):
        return self.is_superuser or bool(self.role_id and self.role.can_manage_users)

    @property
    def can_manage_roles(self):
        return self.is_superuser or bool(self.role_id and self.role.can_manage_roles)

    @property
    def can_view_activity(self):
        return self.is_superuser or bool(self.role_id and self.role.can_view_activity)

    @property
    def is_administration(self):
        return self.can_manage_users or self.can_manage_roles or self.can_view_activity

    # ------------------------------------------------------------- Display
    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        parts = self.display_name.replace('@', ' ').split()
        return ''.join(p[0] for p in parts[:2]).upper() or '?'

    @property
    def role_label(self):
        if self.role_id:
            return self.role.name
        return 'Super Admin' if self.is_superuser else 'No role'

    @property
    def role_color(self):
        if self.role_id:
            return self.role.color
        return 'danger' if self.is_superuser else 'secondary'

class KeywordSearch(models.Model):
    """Stores the main search term, linked to the user, and when it was last updated."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='searches', null=True, blank=True)
    term = models.CharField(max_length=255)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.term} (User: {self.user.username if self.user else 'System'})"

class KeywordResult(models.Model):
    """Stores specific results for a search term to enable caching."""
    search = models.ForeignKey(KeywordSearch, on_delete=models.CASCADE, related_name='results')
    keyword = models.CharField(max_length=255)
    avg_searches = models.IntegerField(default=0)
    avg_clicks = models.IntegerField(default=0)
    avg_ctr = models.FloatField(null=True, blank=True)
    competition = models.IntegerField(default=0)
    kd = models.IntegerField(null=True, blank=True)
    opportunity_score = models.FloatField(default=0.0)
    category = models.CharField(max_length=50) # e.g., 'Dark Green', 'Light Green'
    is_favorite = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.keyword} ({self.search.term})"
