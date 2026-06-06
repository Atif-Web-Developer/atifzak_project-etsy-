from django.urls import path
from . import views

urlpatterns = [
    path('', views.forecaster_dashboard, name='forecaster_dashboard'),
    path('toggle-task/', views.toggle_task, name='forecaster_toggle_task'),
    path('add-event/', views.add_custom_event, name='forecaster_add_event'),
    path('delete-event/<int:event_id>/', views.delete_event, name='forecaster_delete_event'),
]
