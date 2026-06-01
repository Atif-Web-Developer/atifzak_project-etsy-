from django.contrib import admin
from .models import User, KeywordSearch, KeywordResult

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'first_name', 'email', 'is_approved', 'is_premium', 'is_staff')
    list_editable = ('is_approved', 'is_premium')
    list_filter = ('is_approved', 'is_premium', 'is_staff')
    actions = ['approve_users']

    @admin.action(description='Approve selected users')
    def approve_users(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"Successfully approved {updated} users.")

@admin.register(KeywordSearch)
class KeywordSearchAdmin(admin.ModelAdmin):
    list_display = ('term', 'last_updated')

@admin.register(KeywordResult)
class KeywordResultAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'search', 'competition', 'opportunity_score', 'category')
    list_filter = ('category', 'search')
