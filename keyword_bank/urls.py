from django.urls import path
from . import views

app_name = 'keyword_bank'

urlpatterns = [
    path('vault/', views.vault_view, name='keyword_vault'),
    path('deposit/', views.deposit_data, name='deposit_data'),
    path('archive/', views.archive_view, name='archive'),
]
