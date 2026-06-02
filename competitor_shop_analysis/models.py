from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class CompetitorCategory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='competitor_categories')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class CompetitorShop(models.Model):
    category = models.ForeignKey(CompetitorCategory, on_delete=models.CASCADE, related_name='shops')
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.category.name}"

class CompetitorShopData(models.Model):
    shop = models.ForeignKey(CompetitorShop, on_delete=models.CASCADE, related_name='data')
    keyword = models.CharField(max_length=255)
    volume = models.IntegerField(default=0)
    competition = models.IntegerField(default=0)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.keyword} ({self.shop.name})"
