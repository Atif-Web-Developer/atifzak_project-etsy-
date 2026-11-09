from django.contrib import admin

from .models import DropshipSettings, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('item_id', 'product_name', 'tab', 'status', 'listed_price', 'sync_status', 'updated_at')
    list_filter = ('tab', 'status', 'sync_status')
    search_fields = ('item_id', 'product_name', 'seller_name')


@admin.register(DropshipSettings)
class DropshipSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'ebay_fee_pct', 'ebay_fixed_fee', 'ad_rate_pct', 'last_sync_at')
