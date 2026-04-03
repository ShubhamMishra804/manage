from django import template
from finance.utils import format_indian_currency

register = template.Library()

@register.filter(name='indian_currency')
def indian_currency(value):
    """
    Template filter to format currency in Indian Numbering System.
    Usage: {{ amount|indian_currency }}
    """
    try:
        return format_indian_currency(value)
    except Exception:
        return value
