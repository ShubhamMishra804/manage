from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.add_transaction, name='add_transaction'),
    path('history/', views.transaction_history, name='transaction_history'),
    path('debt/add/', views.add_debt, name='add_debt'),
    path('debt/plan/', views.debt_plan, name='debt_plan'),
    path('debt/update/', views.update_debt_payment, name='update_debt_payment'),
    path('debt/log-payment/', views.log_debt_payment, name='log_debt_payment'),
    path('debt/edit/<int:pk>/', views.edit_debt, name='edit_debt'),
    path('debt/planner/', views.repayment_planner, name='repayment_planner'),
    path('debt/planner/advice/', views.get_planner_advice, name='get_planner_advice'),
    path('debt/planner/save/', views.save_planner_goal, name='save_planner_goal'),
    path('transactions/delete/', views.delete_transactions, name='delete_transactions'),
]
