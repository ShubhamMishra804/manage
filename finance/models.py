from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Category(models.Model):
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=7, choices=CATEGORY_TYPES, default='expense')
    icon = models.CharField(max_length=50, blank=True, help_text="Optional icon identifier")

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_type_display()})"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=7, choices=TRANSACTION_TYPES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()}: ₹{self.amount} - {self.description}"


class Debt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='debts')
    name = models.CharField(max_length=200)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Annual interest rate %")
    tenure_months = models.PositiveIntegerField(default=12, help_text="Planned repayment duration in months")
    minimum_payment = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - ₹{self.total_amount}"

    @property
    def remaining(self):
        return max(0, self.total_amount - self.amount_paid)

    @property
    def progress_percent(self):
        if self.total_amount == 0:
            return 100
        percent = (self.amount_paid / self.total_amount) * 100
        return min(100, round(float(percent), 1))
