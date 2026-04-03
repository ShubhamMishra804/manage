from django.contrib import admin
from .models import Category, Transaction, Debt

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type')

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'transaction_type', 'category', 'amount', 'date')
    list_filter = ('transaction_type', 'date')

@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'total_amount', 'amount_paid', 'interest_rate')
