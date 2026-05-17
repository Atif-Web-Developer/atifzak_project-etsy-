from django.urls import path
from . import views

urlpatterns = [
    path('design-lab/', views.design_lab, name='design_lab'),
    path('get-ai-suggestions/', views.get_ai_suggestions, name='get_ai_suggestions'),
    path('ai-smart-generate/', views.ai_smart_generate, name='ai_smart_generate'),
]
