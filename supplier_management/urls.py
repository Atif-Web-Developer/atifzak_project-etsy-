from django.urls import path
from . import views

app_name = 'supplier_management'

urlpatterns = [
    # AJAX
    path('ajax/load-states/', views.load_states, name='ajax_load_states'),

    # Supplier CRUD
    path('', views.supplier_list, name='supplier_list'),
    path('add/', views.supplier_add, name='supplier_add'),
    path('<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),

    # Manage Data (Categories / Countries / States)
    path('manage/', views.manage_data, name='manage_data'),

    # Category
    path('manage/category/add/', views.category_add, name='category_add'),
    path('manage/category/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Country
    path('manage/country/add/', views.country_add, name='country_add'),
    path('manage/country/<int:pk>/delete/', views.country_delete, name='country_delete'),

    # State
    path('manage/state/add/', views.state_add, name='state_add'),
    path('manage/state/<int:pk>/delete/', views.state_delete, name='state_delete'),
]
