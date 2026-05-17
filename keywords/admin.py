from django.contrib import admin
from .models import User, KeywordSearch, KeywordResult

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_premium', 'is_staff')

@admin.register(KeywordSearch)
class KeywordSearchAdmin(admin.ModelAdmin):
    list_display = ('term', 'last_updated')

@admin.register(KeywordResult)
class KeywordResultAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'search', 'competition', 'opportunity_score', 'category')
    list_filter = ('category', 'search')
