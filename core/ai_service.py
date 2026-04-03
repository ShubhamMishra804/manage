import os
from django.conf import settings
from finance.utils import get_financial_summary
from finance.models import Transaction
from django.db.models import Sum, Q


def get_groq_client():
    """Initialize and return the Groq client. Returns None if API key is missing."""
    api_key = os.environ.get('GROQ_API_KEY', '')
    if not api_key:
        return None
    try:
        from groq import Groq
        return Groq(api_key=api_key)
    except Exception as e:
        print(f"[AI Service] Failed to init Groq: {e}")
        return None


MODEL_NAME = "llama-3.3-70b-versatile"


def build_financial_context(user):
    """Build a financial context string from the user's data for AI prompting."""
    summary = get_financial_summary(user)
    recent_txns = Transaction.objects.filter(user=user)[:10]

    # Category spending breakdown
    category_spending = (
        Transaction.objects
        .filter(user=user, transaction_type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    from finance.utils import format_indian_currency
    context_parts = [
        f"User's Financial Summary:",
        f"- Total Income: {format_indian_currency(summary['total_income'])}",
        f"- Total Expenses: {format_indian_currency(summary['total_expenses'])}",
        f"- Current Balance: {format_indian_currency(summary['balance'])}",
        "",
        "Top Spending Categories:",
    ]

    for cat in category_spending:
        name = cat['category__name'] or 'Uncategorized'
        context_parts.append(f"- {name}: {format_indian_currency(cat['total'])}")

    if recent_txns:
        context_parts.append("")
        context_parts.append("Recent Transactions:")
        for txn in recent_txns[:5]:
            sign = '+' if txn.transaction_type == 'income' else '-'
            context_parts.append(
                f"- {txn.date.strftime('%d %b')}: {sign}{format_indian_currency(txn.amount)} ({txn.description or 'No description'})"
            )

    return "\n".join(context_parts)


def get_ai_chat_response(user, user_message):
    """Get a personalized financial advice response from Groq."""
    client = get_groq_client()
    if client is None:
        return {
            'success': False,
            'message': "🌙 AI is sleeping — please add your GROQ_API_KEY in the .env file to wake it up!"
        }

    try:
        financial_context = build_financial_context(user)

        system_prompt = """You are a friendly, professional financial advisor assistant for an Indian user.
You give concise, actionable advice based on their real financial data.
Your responses MUST be formatted as a concise bulleted list of points (using • or -).
Keep the overall response short and avoid long paragraphs.
Use the Indian Numbering System (Lakhs/Crores) for all currency values (e.g., ₹1,23,456).
Add relevant emoji sparingly for warmth."""

        user_prompt = f"""{financial_context}

User's Question: {user_message}

Provide your advice in clear bullet points:"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=300,
        )

        return {
            'success': True,
            'message': response.choices[0].message.content,
        }
    except Exception as e:
        error_msg = str(e)
        print(f"[AI Chat Error] {error_msg}")
        return {
            'success': False,
            'message': f"⚠️ AI Error: {error_msg}"
        }


def get_financial_tip(user):
    """Generate a one-sentence 'Tip of the Day' based on highest spending category."""
    client = get_groq_client()

    # Find highest spending category
    top_category = (
        Transaction.objects
        .filter(user=user, transaction_type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
        .first()
    )

    if not top_category or not top_category['category__name']:
        fallback_tip = "💡 Start tracking your expenses to get personalized AI tips!"
        return fallback_tip

    category_name = top_category['category__name']
    amount = top_category['total']

    if client is None:
        from finance.utils import format_indian_currency
        return f"💡 Your highest spending is on {category_name} ({format_indian_currency(amount)}). Add your GROQ_API_KEY for personalized AI tips!"

    try:
        from finance.utils import format_indian_currency
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a friendly financial advisor. Give ONE short, specific, actionable tip (max 15 words) as a single sentence. Do NOT use bullet points. Use the Indian Numbering System (Lakhs/Crores) for currency (e.g. ₹1,23,456). Be warm. Start with a relevant emoji."},
                {"role": "user", "content": f'The user\'s highest spending category is "{category_name}" at {format_indian_currency(amount)}. Give a single punchy tip sentence.'},
            ],
            temperature=0.7,
            max_tokens=60,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI Tip Error] {e}")
        from finance.utils import format_indian_currency
        return f"💡 Your top spend: {category_name} at {format_indian_currency(amount)}. Consider setting a monthly limit!"
def get_debt_strategy_advice(user, amount, rate, tenure, monthly_payment):
    """Generate personalized advice for a specific debt simulation."""
    client = get_groq_client()
    if not client:
        return "💡 Consider your monthly income. Aim for a payment that doesn't exceed 20% of your take-home pay."

    try:
        from finance.utils import format_indian_currency
        context = build_financial_context(user)
        
        prompt = f"""{context}
        
        Simulation Scenario:
        - Debt Amount: {format_indian_currency(amount)}
        - Interest Rate: {rate}%
        - Tenure: {tenure} months
        - Calculated EMI: {format_indian_currency(monthly_payment)}
        
        Provide exactly 2-3 concise bullet points (using •) of tactical advice. Should the user increase tenure to lower EMI, or shorten it to save interest? Is this EMI too high for their current balance? Be specific and encouraging. Use Indian Numbering System."""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a professional Indian debt coach. You MUST provide your advice in exactly 2-3 bullet points, each on a NEW LINE starting with •. Be specific and concise."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[AI Strategy Error] {e}")
        return "💡 Shortening your tenure can save you significant interest in the long run if your budget allows."
