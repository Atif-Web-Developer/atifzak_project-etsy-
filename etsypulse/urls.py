from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='etsypulse_dashboard'),
    path('upload/', views.upload_file_view, name='etsypulse_upload'),
    path('filter/', views.filter_keywords_ajax, name='etsypulse_filter'),
    path('export/', views.export_filtered_data, name='etsypulse_export'),
]
