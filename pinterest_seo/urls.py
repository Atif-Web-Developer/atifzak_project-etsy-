from django.urls import path
from . import views

urlpatterns = [
    path('', views.pinterest_tool_view, name='pinterest_tool'),
    path('generate/', views.generate_pinterest_seo, name='generate_pinterest_seo'),
]
