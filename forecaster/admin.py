from django.contrib import admin
from .models import ForecastEvent, ForecastTaskProgress

@admin.register(ForecastEvent)
class ForecastEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'month', 'day', 'target_regions', 'sourcing_days_prior', 'design_days_prior', 'is_system_default')
    list_filter = ('is_system_default', 'target_regions')
    search_fields = ('name', 'target_regions', 'aesthetic_vibe')
    ordering = ('month', 'day')

@admin.register(ForecastTaskProgress)
class ForecastTaskProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'task_name', 'is_completed', 'updated_at')
    list_filter = ('is_completed', 'task_name')
    search_fields = ('user__username', 'event__name', 'task_name')

