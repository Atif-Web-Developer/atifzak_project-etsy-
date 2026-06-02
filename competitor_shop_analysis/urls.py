from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='competitor_shop_dashboard'),
    path('add-category/', views.add_category_view, name='competitor_add_category'),
    path('category/<int:cat_id>/edit/', views.edit_category_view, name='competitor_edit_category'),
    path('category/<int:cat_id>/delete/', views.delete_category_view, name='competitor_delete_category'),
    path('add-shop/', views.add_shop_view, name='competitor_add_shop'),
    path('shop/<int:shop_id>/edit/', views.edit_shop_view, name='competitor_edit_shop'),
    path('shop/<int:shop_id>/delete/', views.delete_shop_view, name='competitor_delete_shop'),
    path('add-shop-upload-ajax/', views.add_shop_upload_ajax, name='competitor_add_shop_upload_ajax'),
    path('upload-csv/', views.upload_csv_view, name='competitor_upload_csv'),
    path('shop/<int:shop_id>/', views.view_shop_data, name='competitor_view_shop'),
    path('filter-ajax/', views.filter_shop_data_ajax, name='competitor_filter_ajax'),
    path('toggle-favorite/', views.toggle_favorite_ajax, name='competitor_toggle_favorite'),
    path('export-csv/', views.export_shop_data_csv, name='competitor_export_csv'),
]
