from django.contrib import admin

from .models import ActivityLog, Notification, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'can_manage_users', 'can_manage_roles', 'is_system')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'level', 'is_read', 'created_at')
    list_filter = ('level', 'is_read')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'user', 'ip_address', 'created_at')
    list_filter = ('action',)
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
