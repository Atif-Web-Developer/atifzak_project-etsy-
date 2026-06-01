from django.urls import path
from . import views

app_name = 'customer_detail'

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('list/', views.customer_list, name='customer_list'),
    path('create/', views.customer_create, name='customer_create'),
    path('<int:pk>/', views.customer_view, name='customer_view'),
    path('<int:pk>/edit/', views.customer_update, name='customer_update'),
    path('<int:pk>/delete/', views.customer_delete, name='customer_delete'),
]
