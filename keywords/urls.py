from django.urls import path
from . import views

urlpatterns = [
    path('', views.overview_dashboard, name='overview'),
    path('analyzer/', views.dashboard_view, name='dashboard'),
    path('analyze/', views.analyze_keyword, name='analyze'),
    path('upload-csv/', views.upload_csv, name='upload_csv'),
    path('history/', views.history_view, name='view_history'),
    path('load-results/<int:search_id>/', views.load_results, name='load_results'),
    path('delete-history/<int:search_id>/', views.delete_history, name='delete_history'),
    path('toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('saved/', views.saved_keywords, name='saved_keywords'),
    path('export/', views.export_csv, name='export'),
]
