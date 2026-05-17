from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='rank_optimizer_dashboard'),
    path('upload/', views.upload_file_view, name='rank_optimizer_upload'),
    path('filter/', views.filter_keywords_ajax, name='rank_optimizer_filter'),
    path('export/', views.export_filtered_data, name='rank_optimizer_export'),
]
