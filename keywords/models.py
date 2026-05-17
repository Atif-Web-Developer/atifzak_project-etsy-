from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """Custom user model for future scaling (e.g., Premium features)."""
    is_premium = models.BooleanField(default=False)

class KeywordSearch(models.Model):
    """Stores the main search term and when it was last updated."""
    term = models.CharField(max_length=255, unique=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.term

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
