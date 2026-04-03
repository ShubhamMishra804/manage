from django.core.management.base import BaseCommand
from finance.models import Category


class Command(BaseCommand):
    help = 'Seed default categories for transactions'

    def handle(self, *args, **options):
        categories = [
            ('Salary', 'income'),
            ('Freelance', 'income'),
            ('Investment', 'income'),
            ('Other Income', 'income'),
            ('Food & Dining', 'expense'),
            ('Rent', 'expense'),
            ('Transport', 'expense'),
            ('Entertainment', 'expense'),
            ('Shopping', 'expense'),
            ('Bills & Utilities', 'expense'),
            ('Healthcare', 'expense'),
            ('Education', 'expense'),
            ('Other Expense', 'expense'),
        ]

        created = 0
        for name, cat_type in categories:
            _, was_created = Category.objects.get_or_create(
                name=name,
                defaults={'category_type': cat_type}
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'Done! {created} categories created.'))
