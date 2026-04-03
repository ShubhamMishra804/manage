from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json


def dashboard(request):
    context = {
        'stats': {
            'total_balance': '₹0',
            'monthly_spend': '₹0',
            'monthly_income': '₹0',
            'total_savings': '₹0',
        },
        'monthly_spending': {
            'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            'data': [0, 0, 0, 0, 0, 0],
        },
        'recent_transactions': [],
        'ai_tip': '💡 Log in and start tracking expenses to unlock AI-powered insights!',
    }

    if request.user.is_authenticated:
        from finance.utils import get_financial_summary, get_monthly_spending
        from finance.models import Transaction
        from .ai_service import get_financial_tip

        summary = get_financial_summary(request.user)
        monthly = get_monthly_spending(request.user)
        recent = Transaction.objects.filter(user=request.user)[:5]

        context['stats'] = {
            'total_balance': summary['balance'],
            'monthly_spend': summary['total_expenses'],
            'monthly_income': summary['total_income'],
            'total_savings': max(0, summary['balance']),
        }
        context['monthly_spending'] = monthly
        context['recent_transactions'] = recent
        context['ai_tip'] = get_financial_tip(request.user)

    if request.headers.get('X-PJAX'):
        return render(request, 'dashboard.html', context)
    return render(request, 'dashboard.html', context)


@login_required
@require_POST
def ai_chat(request):
    """AJAX endpoint for AI chat — accepts JSON POST, returns JSON response."""
    try:
        body = json.loads(request.body)
        user_message = body.get('message', '').strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    if not user_message:
        return JsonResponse({'success': False, 'message': 'Please type a message.'}, status=400)

    from .ai_service import get_ai_chat_response
    result = get_ai_chat_response(request.user, user_message)
    return JsonResponse(result)

@login_required
def sidebar_data(request):
    """API endpoint for sidebar widget data (fast)."""
    from finance.utils import get_debt_summary, format_indian_currency
    debt_summary = get_debt_summary(request.user)
    total_debt = debt_summary['total_debt']
    total_paid = debt_summary['total_paid']
    progress = (total_paid / total_debt * 100) if total_debt > 0 else 0
    return JsonResponse({
        'total_debt': format_indian_currency(total_debt),
        'total_paid': format_indian_currency(total_paid),
        'progress': round(progress, 1),
        'remaining': format_indian_currency(debt_summary['total_remaining']),
    })


@login_required
def debt_modal_data(request):
    """API endpoint for detailed debt modal (includes AI advice)."""
    from finance.utils import get_debt_summary, generate_repayment_schedule
    from .ai_service import get_groq_client, MODEL_NAME

    debt_summary = get_debt_summary(request.user)
    schedule_data = generate_repayment_schedule(request.user)

    ai_advice = "No debts to analyze!"
    if debt_summary['total_remaining'] > 0:
        try:
            client = get_groq_client()
            if client:
                power = schedule_data.get('power_data', {})
                from finance.utils import format_indian_currency
                prompt = f"""The user has these debts:
{chr(10).join(f"- {d['name']}: {format_indian_currency(d['remaining'])} at {d['interest_rate']}%" for d in debt_summary['debts'])}
Repayment power: {format_indian_currency(power.get('repayment_power', 0))}
Months to freedom: {schedule_data.get('months_to_freedom', 'unknown')}
Give 3 bullet points of specific advice. IMPORTANT: Use the Indian Numbering System (Lakhs/Crores) for all money values (e.g. ₹1,00,000)."""
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                )
                ai_advice = response.choices[0].message.content
        except Exception as e:
            ai_advice = f"AI currently unavailable: {str(e)}"

    return JsonResponse({
        'debts': debt_summary['debts'],
        'schedule': schedule_data.get('schedule', []),
        'months': schedule_data.get('months_to_freedom', 0),
        'ai_advice': ai_advice,
    })
