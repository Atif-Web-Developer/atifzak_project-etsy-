from django.db import models
from django.conf import settings

class SavedDesign(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    design_image = models.ImageField(upload_to='designs/')
    mockup_style = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s design - {self.created_at}"
