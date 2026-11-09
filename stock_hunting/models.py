import secrets

from django.conf import settings
from django.db import models

# Step 1 – the market sets the eBay site, the currency and where AliExpress must ship to.
MARKETS = {
    'US': {'label': 'USA', 'site': 'ebay.com', 'currency': '$', 'code': 'USD'},
    'UK': {'label': 'UK', 'site': 'ebay.co.uk', 'currency': '£', 'code': 'POUND'},
    'AU': {'label': 'Australia', 'site': 'ebay.com.au', 'currency': 'A$', 'code': 'AUD'},
}
YES_NO = [('Yes', 'Yes'), ('No', 'No')]


class StockSettings(models.Model):
    """Single row: the hunting rules (editable) and the Google Sheet connection."""

    price_min = models.DecimalField('Lowest selling price', max_digits=8, decimal_places=2, default=13)
    price_max = models.DecimalField('Highest selling price', max_digits=8, decimal_places=2, default=35)
    min_sales_30d = models.PositiveIntegerField('30-day sales that count as strong', default=100)
    min_strong_sellers = models.PositiveIntegerField('Sellers needed with those sales', default=2)
    max_feedback = models.PositiveIntegerField('Feedback below this = room for a new seller', default=2000)
    min_low_feedback_sellers = models.PositiveIntegerField('Sellers needed below that feedback', default=1)
    top_sellers = models.PositiveIntegerField('Competitors to note (all different)', default=5)
    ali_min_rating = models.DecimalField('AliExpress minimum rating', max_digits=3, decimal_places=1, default=4.5)
    ali_min_sales = models.PositiveIntegerField('AliExpress minimum sales', default=1000)
    max_total_sellers = models.PositiveIntegerField('Total sellers – fewer is better (up to)', default=50)
    min_orders_per_day = models.DecimalField('Test: orders per day to source', max_digits=5, decimal_places=2, default=1)

    sheet_webapp_url = models.URLField('Google Apps Script web app URL', max_length=500, blank=True)
    sync_token = models.CharField(max_length=64, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_message = models.CharField(max_length=255, blank=True)

    RULE_FIELDS = ('price_min', 'price_max', 'min_sales_30d', 'min_strong_sellers', 'max_feedback',
                   'min_low_feedback_sellers', 'top_sellers', 'ali_min_rating', 'ali_min_sales',
                   'max_total_sellers', 'min_orders_per_day')

    class Meta:
        verbose_name = verbose_name_plural = 'Stock hunting settings'

    def __str__(self):
        return 'Stock hunting settings'

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


class Hunt(models.Model):
    """One product idea – exactly ma'am's two tabs:
    "Product selection" (the fields below) and "Competitors selection" (the competitors list, same Sr. No)."""

    MARKET_CHOICES = [(k, v['label']) for k, v in MARKETS.items()]
    TRENDS = [('Up', 'Up'), ('Stable', 'Stable'), ('Down', 'Down')]
    SYNC_CHOICES = [('synced', 'Synced'), ('pending', 'Waiting to sync'), ('error', 'Sync failed')]

    # ---- Product selection
    sr_no = models.PositiveIntegerField('Sr. No', unique=True)
    main_keyword = models.CharField('Main Keyword', max_length=200)
    sales_trend = models.CharField('Sales Trend', max_length=10, choices=TRENDS, blank=True)
    two_sellers_100 = models.CharField('2 Sellers with 100 above sales { Yes / no}', max_length=3, choices=YES_NO, blank=True)
    avg_price = models.DecimalField('Avg sales price { USD/ POUND }', max_digits=10, decimal_places=2, null=True, blank=True)
    market = models.CharField('Currency', max_length=2, choices=MARKET_CHOICES, default='US')
    total_sellers = models.PositiveIntegerField('Total Sellers', null=True, blank=True)
    seller_listing_link = models.URLField('seller listing link', max_length=1000, blank=True)
    # ---- Competitors selection: [{link, feedback, price, sales_30d, variation}]
    competitors = models.JSONField(default=list, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='stock_hunts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(max_length=10, choices=SYNC_CHOICES, default='pending')
    sync_error = models.CharField(max_length=255, blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sr_no']

    def __str__(self):
        return f'{self.sr_no}. {self.main_keyword}'

    @classmethod
    def next_sr_no(cls):
        last = cls.objects.order_by('-sr_no').values_list('sr_no', flat=True).first()
        return (last or 0) + 1

    @property
    def market_info(self):
        return MARKETS.get(self.market, MARKETS['US'])

    def evaluate(self, conf=None):
        from .rules import evaluate
        return evaluate(self, conf or StockSettings.load())
