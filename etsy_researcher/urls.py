from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.auth_urls')),
    path('account/', include('accounts.urls')),
    path('', include('keywords.urls')),
    path('mockups/', include('mockups.urls')),
    path('bank/', include('keyword_bank.urls')),
    path('profit/', include('profit_pulse.urls')),
    path('optimizer/', include('rank_optimizer.urls')),
    path('pinterest/', include('pinterest_seo.urls')),
    path('customers/', include('customer_detail.urls')),
    path('competitor_shops/', include('competitor_shop_analysis.urls')),
    path('forecaster/', include('forecaster.urls')),
    path('suppliers/', include('supplier_management.urls')),
    path('ebay/', include('ebay_dropshipping.urls')),
    path('stock/', include('stock_hunting.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'accounts.views.permission_denied'
handler404 = 'accounts.views.page_not_found'
handler500 = 'accounts.views.server_error'
