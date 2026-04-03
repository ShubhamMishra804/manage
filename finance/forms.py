from django import forms
from .models import Transaction, Category, Debt


class TransactionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = Transaction
        fields = ['transaction_type', 'category', 'amount', 'description', 'date']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2.5 rounded-xl bg-earth-100 dark:bg-earth-800 border border-earth-200 dark:border-earth-700 text-earth-800 dark:text-earth-100 focus:outline-none focus:ring-2 focus:ring-terra-500 focus:border-transparent transition'
            })


class DebtForm(forms.ModelForm):
    class Meta:
        model = Debt
        fields = ['name', 'total_amount', 'amount_paid', 'interest_rate', 'minimum_payment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = 'e.g. Home Loan, Credit Card'
        self.fields['total_amount'].widget.attrs['placeholder'] = 'Total debt amount'
        self.fields['amount_paid'].widget.attrs['placeholder'] = 'Amount already paid'
        self.fields['interest_rate'].widget.attrs['placeholder'] = 'Annual interest %'
        self.fields['minimum_payment'].widget.attrs['placeholder'] = 'Monthly minimum'
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'w-full px-3 py-2.5 rounded-xl bg-earth-100 dark:bg-earth-800 border border-earth-200 dark:border-earth-700 text-earth-800 dark:text-earth-100 focus:outline-none focus:ring-2 focus:ring-terra-500 focus:border-transparent transition'
            })
