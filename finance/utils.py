from django.db.models import Sum, Q
from .models import Transaction, Debt


def format_indian_currency(number, include_symbol=True):
    """
    Format a number into Indian Numbering System (Lakhs/Crores).
    123456 -> 1,23,456
    """
    if number is None:
        return "₹0" if include_symbol else "0"
    
    try:
        n = float(number)
    except (ValueError, TypeError):
        return str(number)

    minus = "-" if n < 0 else ""
    n = abs(n)

    # Use .2f to handle floats, then split into integer and decimal parts
    s = f"{n:.2f}"
    main_part, dec_part = s.split('.')
    dec = f".{dec_part}" if dec_part != "00" else ""
    
    if len(main_part) <= 3:
        res = main_part
    else:
        last_three = main_part[-3:]
        remaining = main_part[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        res = ",".join(reversed(groups)) + "," + last_three
    
    formatted = f"{minus}{res}{dec}"
    return f"₹{formatted}" if include_symbol else formatted


def get_financial_summary(user):
    """Calculate total balance, income, expenses for a user."""
    totals = Transaction.objects.filter(user=user).aggregate(
        total_income=Sum('amount', filter=Q(transaction_type='income')),
        total_expenses=Sum('amount', filter=Q(transaction_type='expense')),
    )

    total_income = totals['total_income'] or 0
    total_expenses = totals['total_expenses'] or 0
    balance = total_income - total_expenses

    return {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
    }


def get_monthly_spending(user, months=6):
    """Get monthly spending data for chart rendering."""
    from django.utils import timezone
    from datetime import timedelta
    import calendar

    today = timezone.now().date()
    labels = []
    data = []

    for i in range(months - 1, -1, -1):
        # Calculate the month
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1

        month_name = calendar.month_abbr[month]
        labels.append(month_name)

        total = Transaction.objects.filter(
            user=user,
            transaction_type='expense',
            date__year=year,
            date__month=month,
        ).aggregate(total=Sum('amount'))['total'] or 0

        data.append(float(total))

    return {'labels': labels, 'data': data}


def get_debt_summary(user):
    """Get debt progress data."""
    debts = Debt.objects.filter(user=user)
    debt_list = []
    for debt in debts:
        debt_list.append({
            'name': debt.name,
            'total': float(debt.total_amount),
            'paid': float(debt.amount_paid),
            'remaining': float(debt.remaining),
            'progress': debt.progress_percent,
            'interest_rate': float(debt.interest_rate),
            'min_payment': float(debt.minimum_payment),
        })

    total_debt = sum(d['total'] for d in debt_list)
    total_paid = sum(d['paid'] for d in debt_list)

    return {
        'debts': debt_list,
        'total_debt': total_debt,
        'total_paid': total_paid,
        'total_remaining': max(0, total_debt - total_paid),
    }


def get_repayment_power(user):
    """Calculate disposable income available for debt repayment.
    Repayment Power = Income - Expenses - 10% Emergency Buffer."""
    from django.utils import timezone
    import calendar

    today = timezone.now().date()
    current_month = today.month
    current_year = today.year

    # Monthly income (current month or average)
    monthly_income = Transaction.objects.filter(
        user=user, transaction_type='income',
        date__year=current_year, date__month=current_month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # If no income this month, use average of last 3 months
    if monthly_income == 0:
        total_income_3m = Transaction.objects.filter(
            user=user, transaction_type='income',
        ).aggregate(total=Sum('amount'))['total'] or 0
        count = Transaction.objects.filter(
            user=user, transaction_type='income',
        ).dates('date', 'month').count() or 1
        monthly_income = float(total_income_3m) / count

    # Monthly expenses (average)
    monthly_expenses = Transaction.objects.filter(
        user=user, transaction_type='expense',
        date__year=current_year, date__month=current_month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    if monthly_expenses == 0:
        total_exp_3m = Transaction.objects.filter(
            user=user, transaction_type='expense',
        ).aggregate(total=Sum('amount'))['total'] or 0
        count = Transaction.objects.filter(
            user=user, transaction_type='expense',
        ).dates('date', 'month').count() or 1
        monthly_expenses = float(total_exp_3m) / count

    monthly_income = float(monthly_income)
    monthly_expenses = float(monthly_expenses)

    emergency_buffer = monthly_income * 0.10
    repayment_power = max(0, monthly_income - monthly_expenses - emergency_buffer)

    return {
        'monthly_income': monthly_income,
        'monthly_expenses': monthly_expenses,
        'emergency_buffer': emergency_buffer,
        'repayment_power': repayment_power,
    }


def generate_repayment_schedule(user):
    """Generate a month-by-month repayment schedule using a Hybrid Strategy.
    Phase 1: Snowball (Prioritize 2 smallest debts for motivation)
    Phase 2: Avalanche (Prioritize remaining debts by highest interest rate)"""
    from .models import Debt
    import math

    all_debts = list(Debt.objects.filter(user=user))
    if not all_debts:
        return {'schedule': [], 'months_to_freedom': 0, 'total_interest_saved': 0}

    power_data = get_repayment_power(user)
    monthly_power = power_data['repayment_power']

    if monthly_power <= 0:
        return {
            'schedule': [],
            'months_to_freedom': -1,  # Cannot repay
            'total_interest_saved': 0,
            'power_data': power_data,
        }

    # Build working copy of debts with current remaining balances
    working_debts = []
    for d in all_debts:
        remaining = float(d.total_amount) - float(d.amount_paid)
        if remaining > 0:
            working_debts.append({
                'id': d.id,
                'name': d.name,
                'remaining': remaining,
                'interest_rate': float(d.interest_rate),
                'min_payment': float(d.minimum_payment),
                'monthly_rate': float(d.interest_rate) / 100 / 12,
            })

    if not working_debts:
        return {'schedule': [], 'months_to_freedom': 0, 'power_data': power_data}

    # Identify Phase 1 (Snowball) Targets: The 2 smallest remaining balances
    # We sort by remaining balance ascending to find the smallest ones.
    temp_sorted = sorted(working_debts, key=lambda x: x['remaining'])
    snowball_ids = [d['id'] for d in temp_sorted[:2]] if len(temp_sorted) > 2 else []

    # Final Sort Order:
    # 1. Snowball targets first (to build motivation)
    # 2. Then by interest rate descending (Avalanche efficiency)
    def hybrid_sort_key(debt):
        is_snowball = 1 if debt['id'] in snowball_ids else 0
        # Multi-level sort: Snowball status (desc 1->0), then Interest (desc)
        return (-is_snowball, -debt['interest_rate'])

    working_debts.sort(key=hybrid_sort_key)

    schedule = []
    month = 0
    max_months = 480  # 40 year cap for edge cases

    while any(d['remaining'] > 0 for d in working_debts) and month < max_months:
        month += 1
        month_data = {'month': month, 'payments': [], 'total_payment': 0}
        available = monthly_power

        # Step 1: Pay minimum on all active debts
        for debt in working_debts:
            if debt['remaining'] <= 0:
                continue
            # Add interest for the month
            interest = debt['remaining'] * debt['monthly_rate']
            debt['remaining'] += interest
            
            # Pay minimum payment
            payment = min(debt['min_payment'], debt['remaining'])
            debt['remaining'] -= payment
            available -= payment
            
            month_data['payments'].append({
                'name': debt['name'],
                'debt_id': debt['id'],
                'payment': round(payment, 0),
                'remaining': round(max(0, debt['remaining']), 0),
            })
            month_data['total_payment'] += payment

        # Step 2: Allocate extra repayment power (Avalanche or Snowball prioritized)
        # We use the same sorted order established above.
        for debt in working_debts:
            if debt['remaining'] <= 0 or available <= 0:
                continue
            
            extra = min(available, debt['remaining'])
            debt['remaining'] -= extra
            available -= extra
            
            # Update the payment record in month_data
            for p in month_data['payments']:
                if p['debt_id'] == debt['id']:
                    p['payment'] += round(extra, 0)
                    p['remaining'] = round(max(0, debt['remaining']), 0)
                    break
            month_data['total_payment'] += extra

        month_data['total_payment'] = round(month_data['total_payment'], 0)
        schedule.append(month_data)

    return {
        'schedule': schedule[:24],  # Limit display to 24 months
        'months_to_freedom': month if month < max_months else -1,
        'power_data': power_data,
        'is_hybrid': True,
        'snowball_count': len(snowball_ids)
    }

