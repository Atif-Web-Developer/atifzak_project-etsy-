import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .calculations import calculate


class DropshipSettings(models.Model):
    """Single row holding fee settings and the Google Sheet connection."""

    ebay_fee_pct = models.DecimalField('eBay fee %', max_digits=6, decimal_places=2, default=13.6)
    ebay_fixed_fee = models.DecimalField('Fixed fee (order up to threshold)', max_digits=8, decimal_places=2, default=0.30)
    ebay_fixed_fee_high = models.DecimalField('Fixed fee (order above threshold)', max_digits=8, decimal_places=2, default=0.40)
    fixed_fee_threshold = models.DecimalField('Fixed fee threshold', max_digits=8, decimal_places=2, default=10)
    ad_rate_pct = models.DecimalField('Ad rate %', max_digits=6, decimal_places=2, default=5)
    sales_tax_pct = models.DecimalField('Sales tax buffer %', max_digits=6, decimal_places=2, default=0)
    fees_updated_at = models.DateTimeField(default=timezone.now)

    sheet_webapp_url = models.URLField('Google Apps Script web app URL', max_length=500, blank=True)
    sync_token = models.CharField(max_length=64, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_message = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Dropshipping settings'
        verbose_name_plural = 'Dropshipping settings'

    def __str__(self):
        return 'eBay dropshipping settings'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        if not obj.sync_token:
            obj.sync_token = secrets.token_urlsafe(24)
            obj.save(update_fields=['sync_token'])
        return obj

    @property
    def sheet_connected(self):
        return bool(self.sheet_webapp_url and self.sync_token)

    # Fee settings shared with the sheet ("eBay Settings" tab) and the JavaScript calculator.
    FEE_FIELDS = ('ebay_fee_pct', 'ebay_fixed_fee', 'ebay_fixed_fee_high', 'fixed_fee_threshold',
                  'ad_rate_pct', 'sales_tax_pct')

    def fees_dict(self):
        return {name: float(getattr(self, name)) for name in self.FEE_FIELDS}


class UserTabPreference(models.Model):
    """Remembers the last sheet tab each user saved into."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ebay_tab_pref')
    last_tab = models.CharField(max_length=100)


class Product(models.Model):
    STATUS_CHOICES = [
        ('Researching', 'Researching'),
        ('Testing', 'Testing'),
        ('Listed', 'Listed'),
        ('Winning', 'Winning'),
        ('Rejected', 'Rejected'),
    ]
    STATUS_COLORS = {
        'Researching': 'info', 'Testing': 'warning', 'Listed': 'primary',
        'Winning': 'success', 'Rejected': 'danger',
    }
    SYNC_CHOICES = [('synced', 'Synced'), ('pending', 'Waiting to sync'), ('error', 'Sync failed')]

    tab = models.CharField('Sheet tab', max_length=100)

    # Auto-filled from the pasted eBay page
    item_id = models.CharField('ID', max_length=20)
    product_name = models.CharField(max_length=300, blank=True)
    seller_name = models.CharField(max_length=150, blank=True)
    seller_feedback = models.PositiveIntegerField('Total seller feedback count', null=True, blank=True)
    seller_price = models.DecimalField('eBay seller price', max_digits=12, decimal_places=2, null=True, blank=True)
    buyer_shipping = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sold_orders = models.PositiveIntegerField('Sold / orders', null=True, blank=True)
    sales_line = models.CharField(max_length=150, blank=True)
    variation = models.CharField(max_length=50, blank=True)
    image_url = models.URLField('Image', max_length=1000, blank=True,
                                help_text='Product picture (link). Shown as a picture in the Google Sheet.')

    # Typed manually
    supplier_link = models.URLField(max_length=1000, blank=True)
    supplier_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    supplier_shipping = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    other_cost = models.DecimalField('Sourcing buying fee / other cost', max_digits=12, decimal_places=2,
                                     default=0, null=True, blank=True)
    competitor_links = models.TextField(blank=True, help_text='One link per line.')
    competitor_feedbacks = models.PositiveIntegerField('Competitor no. of feedbacks', null=True, blank=True)
    competitor_sold = models.PositiveIntegerField('Competitor solds / orders', null=True, blank=True)
    # Full tables (see lists.py); the single fields above are filled from the ★ / ✓ rows.
    competitors = models.JSONField(default=list, blank=True)
    suppliers = models.JSONField(default=list, blank=True)
    listed_price = models.DecimalField('My listed price', max_digits=12, decimal_places=2, null=True, blank=True)
    my_shipping = models.DecimalField('My shipping charge', max_digits=12, decimal_places=2, default=0,
                                      null=True, blank=True,
                                      help_text='What you charge the buyer for shipping (0 = free shipping).')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Researching')

    # Bookkeeping
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='ebay_products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(max_length=10, choices=SYNC_CHOICES, default='pending')
    sync_error = models.CharField(max_length=255, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [models.UniqueConstraint(fields=['tab', 'item_id'], name='unique_item_per_tab')]

    def __str__(self):
        return f'{self.item_id} – {self.product_name[:40]}'

    @property
    def ebay_link(self):
        return f'https://www.ebay.com/itm/{self.item_id}' if self.item_id else ''

    @property
    def competitor_link_list(self):
        return [line.strip() for line in self.competitor_links.splitlines() if line.strip()]

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    def calc(self, fee_settings=None):
        fee_settings = fee_settings or DropshipSettings.load()
        return calculate(self.listed_price, self.supplier_cost, self.supplier_shipping, self.other_cost,
                         fee_settings, my_shipping=self.my_shipping)
