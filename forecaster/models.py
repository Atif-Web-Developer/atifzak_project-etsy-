from django.db import models
from django.contrib.auth import get_user_model
from datetime import date, timedelta

User = get_user_model()

class ForecastEvent(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='forecast_events', 
        null=True, 
        blank=True
    )
    name = models.CharField(max_length=255)
    month = models.IntegerField()
    day = models.IntegerField()
    target_regions = models.CharField(max_length=255, default='Global')  # e.g. "US, UK, Global"
    sourcing_days_prior = models.IntegerField(default=90)
    design_days_prior = models.IntegerField(default=60)
    niche_categories = models.JSONField(default=list)
    seo_keywords = models.JSONField(default=list)
    aesthetic_vibe = models.TextField(blank=True, null=True)
    target_buyer_profile = models.TextField(blank=True, null=True)
    is_system_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['month', 'day']

    def __str__(self):
        owner = "System" if self.is_system_default else (self.user.username if self.user else "Unknown")
        return f"{self.name} ({owner}) - {self.target_date_label}"

    @property
    def title(self):
        return self.name

    @property
    def regions(self):
        return self.target_regions

    @property
    def target_date(self):
        today = date.today()
        year = today.year
        try:
            target = date(year, self.month, self.day)
        except ValueError:
            target = date(year, 3, 1) # Leap year fallback (Feb 29)
        
        if target < today:
            try:
                target = date(year + 1, self.month, self.day)
            except ValueError:
                target = date(year + 1, 3, 1)
        return target

    @property
    def target_date_label(self):
        return self.target_date.strftime('%B %d')

    @property
    def sourcing_deadline(self):
        return self.target_date - timedelta(days=self.sourcing_days_prior)

    @property
    def design_deadline(self):
        return self.target_date - timedelta(days=self.design_days_prior)

    @property
    def categories_list(self):
        return self.niche_categories

    @property
    def keywords_list(self):
        return self.seo_keywords


class ForecastTaskProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forecast_progress')
    event = models.ForeignKey(ForecastEvent, on_delete=models.CASCADE, related_name='progress')
    task_name = models.CharField(max_length=255)  # e.g. "Market Research", "Product Sourcing", "Design Creation", "SEO Optimization", "Publishing"
    is_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'event', 'task_name')

    def __str__(self):
        status = "Completed" if self.is_completed else "Pending"
        return f"{self.user.username} - {self.event.title} - {self.task_name} ({status})"

