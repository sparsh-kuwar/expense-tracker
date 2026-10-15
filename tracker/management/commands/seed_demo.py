from django.core.management.base import BaseCommand

from tracker.demo import ensure_demo_user


class Command(BaseCommand):
    help = "Create the demo account with 12 months of sample expenses (no-op if current)."

    def handle(self, *args, **options):
        user = ensure_demo_user()
        self.stdout.write(f"Demo user '{user.username}' has {user.expenses.count()} expenses.")
