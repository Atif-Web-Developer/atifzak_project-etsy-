from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),

    path('notifications/', views.notification_list, name='notifications'),
    path('notifications/<int:pk>/open/', views.notification_open, name='notification_open'),
    path('notifications/<int:pk>/delete/', views.notification_delete, name='notification_delete'),
    path('notifications/mark-all-read/', views.notification_mark_all, name='notification_mark_all'),
    path('notifications/clear/', views.notification_clear, name='notification_clear'),

    path('users/', views.user_list, name='user_list'),
    path('users/new/', views.user_create, name='user_create'),
    path('users/<int:pk>/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),

    path('roles/', views.role_list, name='role_list'),
    path('roles/new/', views.role_create, name='role_create'),
    path('roles/<int:pk>/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/delete/', views.role_delete, name='role_delete'),

    path('activity/', views.activity_list, name='activity'),
]
