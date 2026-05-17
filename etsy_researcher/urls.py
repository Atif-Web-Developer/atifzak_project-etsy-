from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('keywords.urls')),
    path('mockups/', include('mockups.urls')),
    path('bank/', include('keyword_bank.urls')),
    path('profit/', include('profit_pulse.urls')),
    path('optimizer/', include('rank_optimizer.urls')),
]
