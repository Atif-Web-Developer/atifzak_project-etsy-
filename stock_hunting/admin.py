from django.contrib import admin

from .models import Hunt, StockSettings


@admin.register(Hunt)
class HuntAdmin(admin.ModelAdmin):
    list_display = ('sr_no', 'main_keyword', 'market', 'sync_status', 'updated_at')
    list_filter = ('market', 'sync_status')
    search_fields = ('main_keyword',)


admin.site.register(StockSettings)
