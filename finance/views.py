from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Transaction, Debt
from .forms import TransactionForm, DebtForm
from .utils import get_financial_summary, get_debt_summary, generate_repayment_schedule, format_indian_currency
from core.ai_service import get_debt_strategy_advice
import json
from decimal import Decimal


@login_required
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.save()
            return redirect('transaction_history')
    else:
        form = TransactionForm()

    return render(request, 'finance/add_transaction.html', {'form': form})


@login_required
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user)[:20]
    summary = get_financial_summary(request.user)
    return render(request, 'finance/history.html', {
        'transactions': transactions,
        'summary': summary,
    })


@login_required
def add_debt(request):
    if request.method == 'POST':
        form = DebtForm(request.POST)
        if form.is_valid():
            debt = form.save(commit=False)
            debt.user = request.user
            debt.save()
            return redirect('debt_plan')
    else:
        form = DebtForm()
    return render(request, 'finance/add_debt.html', {'form': form})


@login_required
def debt_plan(request):
    debt_summary = get_debt_summary(request.user)
    schedule_data = generate_repayment_schedule(request.user)
    debts = Debt.objects.filter(user=request.user)

    # Get AI advice if there are debts
    ai_advice = None
    if debt_summary['total_remaining'] > 0:
        try:
            from core.ai_service import get_groq_client, MODEL_NAME
            client = get_groq_client()
            if client:
                power = schedule_data.get('power_data', {})
                from .utils import format_indian_currency
                prompt = f"""The user has these debts (sorted by interest, highest first):
{chr(10).join(f"- {d['name']}: {format_indian_currency(d['remaining'])} remaining at {d['interest_rate']}% interest" for d in debt_summary['debts'])}

Their monthly income: {format_indian_currency(power.get('monthly_income', 0))}
Monthly expenses: {format_indian_currency(power.get('monthly_expenses', 0))}
Repayment power (after 10% emergency buffer): {format_indian_currency(power.get('repayment_power', 0))}
Estimated months to freedom: {schedule_data.get('months_to_freedom', 'unknown')}

Provide exactly 3 concise bullet points (using •) of personalized, actionable debt advice. We are using a Hybrid Strategy. Be specific with numbers. Use the Indian Numbering System (Lakhs/Crores). Each point should be a single, short sentence. Start each point with a relevant emoji after the bullet."""

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a friendly Indian financial advisor. You MUST provide your advice in exactly 3 bullet points, each on a NEW LINE starting with •. Be specific and concise."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=200,
                )
                ai_advice = response.choices[0].message.content.strip()
        except Exception as e:
            ai_advice = f"⚠️ AI advice unavailable: {str(e)}"

    return render(request, 'finance/debt_plan.html', {
        'debt_summary': debt_summary,
        'schedule': schedule_data.get('schedule', []),
        'months_to_freedom': schedule_data.get('months_to_freedom', 0),
        'power_data': schedule_data.get('power_data', {}),
        'debts': debts,
        'ai_advice': ai_advice,
    })


@login_required
def update_debt_payment(request):
    """AJAX endpoint to update a debt's paid amount (absolute)."""
    if request.method == 'POST':
        try:
            from decimal import Decimal
            body = json.loads(request.body)
            debt_id = body.get('debt_id')
            new_paid = Decimal(str(body.get('amount_paid', 0)))
            debt = Debt.objects.get(id=debt_id, user=request.user)
            debt.amount_paid = new_paid
            debt.save()
            return JsonResponse({
                'success': True,
                'progress': float(debt.progress_percent),
                'remaining': float(debt.remaining),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@login_required
def log_debt_payment(request):
    """AJAX endpoint to increment a debt's paid amount (incremental)."""
    if request.method == 'POST':
        try:
            from decimal import Decimal
            from .utils import get_debt_summary, generate_repayment_schedule, format_indian_currency
            body = json.loads(request.body)
            debt_id = body.get('debt_id')
            payment_amount = Decimal(str(body.get('payment_amount', 0)))
            
            debt = Debt.objects.get(id=debt_id, user=request.user)
            debt.amount_paid += payment_amount
            debt.save()
            
            # Recalculate everything for summary
            debt_summary = get_debt_summary(request.user)
            schedule_data = generate_repayment_schedule(request.user)
            
            return JsonResponse({
                'success': True,
                'new_paid_individual': format_indian_currency(debt.amount_paid),
                'progress_individual': float(debt.progress_percent),
                'remaining_individual': format_indian_currency(debt.remaining),
                'remaining_individual_raw': float(debt.remaining),
                'total_paid': format_indian_currency(debt_summary['total_paid']),
                'total_remaining': format_indian_currency(debt_summary['total_remaining']),
                'months_to_freedom': schedule_data.get('months_to_freedom', 0),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@login_required
def edit_debt(request, pk):
    debt = Debt.objects.get(pk=pk, user=request.user)
    if request.method == 'POST':
        form = DebtForm(request.POST, instance=debt)
        if form.is_valid():
            form.save()
            return redirect('debt_plan')
    else:
        form = DebtForm(instance=debt)
    
    return render(request, 'finance/add_debt.html', {
        'form': form,
        'is_edit': True,
        'debt': debt
    })


@login_required
def repayment_planner(request):
    """Render the interactive debt repayment planner page."""
    return render(request, 'finance/repayment_planner.html')


@login_required
def get_planner_advice(request):
    """AJAX view to fetch AI strategy advice based on simulation inputs."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body or '{}')
            amount = Decimal(str(body.get('amount', 0)))
            rate = Decimal(str(body.get('rate', 0)))
            tenure = int(body.get('tenure', 12))
            emi = Decimal(str(body.get('emi', 0)))
            
            advice = get_debt_strategy_advice(request.user, amount, rate, tenure, emi)
            return JsonResponse({'success': True, 'advice': advice})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)


@login_required
def save_planner_goal(request):
    """AJAX view to save the simulation as a new Debt goal."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body or '{}')
            name = body.get('name', 'Planned Debt Goal')
            amount = Decimal(str(body.get('amount', 0)))
            rate = Decimal(str(body.get('rate', 0)))
            tenure = int(body.get('tenure', 12))
            emi = Decimal(str(body.get('emi', 0)))
            
            Debt.objects.create(
                user=request.user,
                name=name,
                total_amount=amount,
                interest_rate=rate,
                tenure_months=tenure,
                minimum_payment=emi
            )
            return JsonResponse({'success': True, 'message': 'Goal saved successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)
@login_required
def delete_transactions(request):
    """AJAX endpoint to delete one or more transactions."""
    if request.method == 'POST':
        try:
            body = json.loads(request.body or '{}')
            ids = body.get('ids', [])
            if not isinstance(ids, list):
                ids = [ids]
            
            # Filter by user to ensure security
            deleted_count, _ = Transaction.objects.filter(id__in=ids, user=request.user).delete()
            
            # Recalculate summary for the return
            from .utils import get_financial_summary
            summary = get_financial_summary(request.user)
            from .utils import format_indian_currency
            
            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count,
                'new_balance': format_indian_currency(summary['balance']),
                'new_income': format_indian_currency(summary['total_income']),
                'new_expenses': format_indian_currency(summary['total_expenses']),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False}, status=405)
