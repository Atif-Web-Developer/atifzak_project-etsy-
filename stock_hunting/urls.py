from django.urls import path

from . import views

app_name = 'stock_hunting'

urlpatterns = [
    path('', views.hunt_list, name='hunt_list'),
    path('add/', views.hunt_form, name='hunt_add'),
    path('<int:pk>/edit/', views.hunt_form, name='hunt_edit'),
    path('<int:pk>/delete/', views.hunt_delete, name='hunt_delete'),
    path('evaluate/', views.evaluate_view, name='evaluate'),
    path('guide/', views.guide, name='guide'),
    path('sync/', views.sync_now, name='sync'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/rules/', views.save_rules, name='save_rules'),
    path('settings/new-key/', views.regenerate_token, name='regenerate_token'),
    path('script/Code.gs', views.download_script, name='download_script'),
]
