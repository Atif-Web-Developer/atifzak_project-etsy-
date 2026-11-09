from django.urls import path

from . import views

app_name = 'ebay_dropshipping'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.product_form, name='product_add'),
    path('<int:pk>/edit/', views.product_form, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('sync/', views.sync_now, name='sync'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/fees/', views.save_fees, name='save_fees'),
    path('settings/new-key/', views.regenerate_token, name='regenerate_token'),
    path('script/<str:name>', views.download_script, name='download_script'),
]
