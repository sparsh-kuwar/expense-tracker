"""Realistic sample data for the demo account, so the charts have something to show."""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .analytics import month_start
from .models import Expense

DEMO_USERNAME = "demo"

C = Expense.Category
P = Expense.PaymentMode

# (category, description, min amount, max amount, payment modes)
RECURRING = [
    (C.RENT, "Monthly rent", 14000, 14000, [P.NETBANKING]),
    (C.UTILITIES, "Electricity bill", 900, 2200, [P.UPI]),
    (C.UTILITIES, "Mobile & internet", 799, 799, [P.CARD]),
    (C.EDUCATION, "Online course subscription", 499, 499, [P.CARD]),
]
OCCASIONAL = [
    (C.FOOD, "Groceries", 300, 2500, [P.UPI, P.CARD]),
    (C.FOOD, "Dinner with friends", 400, 1800, [P.UPI, P.CARD]),
    (C.FOOD, "Swiggy order", 180, 650, [P.UPI]),
    (C.TRANSPORT, "Uber ride", 120, 600, [P.UPI]),
    (C.TRANSPORT, "Metro card recharge", 500, 500, [P.UPI]),
    (C.TRANSPORT, "Fuel", 1000, 2500, [P.CARD]),
    (C.SHOPPING, "Clothes", 800, 4000, [P.CARD]),
    (C.SHOPPING, "Amazon order", 300, 3500, [P.CARD, P.UPI]),
    (C.HEALTH, "Pharmacy", 150, 900, [P.UPI, P.CASH]),
    (C.ENTERTAINMENT, "Movie tickets", 300, 900, [P.UPI]),
    (C.ENTERTAINMENT, "Netflix", 649, 649, [P.CARD]),
    (C.OTHER, "Gift", 500, 2500, [P.UPI, P.CASH]),
]
OCCASIONAL_WEIGHTS = [10, 4, 8, 6, 2, 3, 2, 3, 2, 2, 1, 1]


def _money(rng, low, high):
    return Decimal(rng.randint(low * 100, high * 100)) / 100 if low != high else Decimal(low)


def generate(user, months=12, seed=42):
    """Create about `months` months of expenses for `user`, ending today."""
    rng = random.Random(seed)
    today = timezone.localdate()
    start = month_start(today, months - 1)
    rows = []

    for back in range(months - 1, -1, -1):
        first = month_start(today, back)
        for cat, desc, low, high, modes in RECURRING:
            day = first + timedelta(days=rng.randint(0, 4))
            if day <= today:
                rows.append(Expense(user=user, date=day, amount=_money(rng, low, high),
                                    category=cat, payment_mode=rng.choice(modes),
                                    description=desc))

    # Spending rises in festive months (Oct-Nov) and dips in mid-year.
    day = start
    while day <= today:
        busy = 1.6 if day.month in (10, 11) else 0.8 if day.month in (6, 7) else 1.0
        for _ in range(rng.choices([0, 1, 2], weights=[3, 5, 2])[0]):
            if rng.random() > busy / 1.6 + 0.2:
                continue
            cat, desc, low, high, modes = rng.choices(OCCASIONAL, OCCASIONAL_WEIGHTS)[0]
            rows.append(Expense(user=user, date=day, amount=_money(rng, low, high),
                                category=cat, payment_mode=rng.choice(modes),
                                description=desc))
        day += timedelta(days=1)

    Expense.objects.bulk_create(rows)
    return len(rows)


@transaction.atomic
def ensure_demo_user():
    """Return the demo user, regenerating its data if it is missing or out of date."""
    User = get_user_model()
    user, created = User.objects.get_or_create(username=DEMO_USERNAME)
    if created:
        user.set_unusable_password()
        user.save()
    latest = user.expenses.order_by("-date").values_list("date", flat=True).first()
    if latest is None or latest < month_start(timezone.localdate()):
        user.expenses.all().delete()
        generate(user)
    return user
