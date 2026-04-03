from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('ai/chat/', views.ai_chat, name='ai_chat'),
    path('api/sidebar-data/', views.sidebar_data, name='sidebar_data'),
    path('api/debt-modal/', views.debt_modal_data, name='debt_modal_data'),
]
