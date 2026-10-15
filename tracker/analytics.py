"""Spending analysis: aggregates and plain-language insights for one user's expenses.

Every function takes a queryset of Expense rows, so the same code works for the
whole history or a filtered subset. All money values are Decimal.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum

from .models import Expense

ZERO = Decimal("0")


def month_start(d: date, months_back: int = 0) -> date:
    """First day of the month that is `months_back` months before d's month."""
    index = d.year * 12 + (d.month - 1) - months_back
    return date(index // 12, index % 12 + 1, 1)


def _total(qs) -> Decimal:
    return qs.aggregate(total=Sum("amount"))["total"] or ZERO


def pct_change(current: Decimal, previous: Decimal):
    """Percentage change from previous to current, or None when previous is zero."""
    if not previous:
        return None
    return float((current - previous) / previous * 100)


def monthly_trend(qs, today: date, months: int = 12):
    """Totals for the last `months` calendar months, oldest first, with empty months as 0."""
    start = month_start(today, months - 1)
    rows = (
        qs.filter(date__gte=start)
        .values("date__year", "date__month")
        .annotate(total=Sum("amount"))
    )
    totals = {(r["date__year"], r["date__month"]): r["total"] for r in rows}
    trend = []
    for back in range(months - 1, -1, -1):
        m = month_start(today, back)
        trend.append({
            "label": m.strftime("%b %Y"),
            "total": totals.get((m.year, m.month), ZERO),
        })
    return trend


def by_category(qs):
    """Total, count and share per category, largest first."""
    labels = dict(Expense.Category.choices)
    rows = list(
        qs.values("category")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    grand = sum((r["total"] for r in rows), ZERO)
    largest = rows[0]["total"] if rows else ZERO
    return [
        {
            "category": r["category"],
            "label": labels.get(r["category"], r["category"]),
            "total": r["total"],
            "count": r["count"],
            "share": float(r["total"] / grand * 100) if grand else 0.0,
            # Bar length relative to the largest category, for the dashboard bars.
            "bar": round(float(r["total"] / largest * 100), 1) if largest else 0.0,
        }
        for r in rows
    ]


def by_payment_mode(qs):
    labels = dict(Expense.PaymentMode.choices)
    rows = qs.values("payment_mode").annotate(total=Sum("amount")).order_by("-total")
    return [
        {"label": labels.get(r["payment_mode"], r["payment_mode"]), "total": r["total"]}
        for r in rows
    ]


def summary(qs, today: date):
    """Headline numbers for the dashboard."""
    this_start = month_start(today)
    last_start = month_start(today, 1)
    this_month = _total(qs.filter(date__gte=this_start, date__lte=today))
    last_month = _total(qs.filter(date__gte=last_start, date__lt=this_start))
    return {
        "this_month": this_month,
        "last_month": last_month,
        "change_pct": pct_change(this_month, last_month),
        "daily_average": this_month / today.day,
        "all_time": _total(qs),
        "count": qs.count(),
    }


def insights(qs, today: date):
    """Short sentences that explain the spending pattern. Empty list when there is no data."""
    if not qs.exists():
        return []
    notes = []

    s = summary(qs, today)
    if s["change_pct"] is not None:
        direction = "more" if s["change_pct"] >= 0 else "less"
        notes.append(
            f"You have spent {abs(s['change_pct']):.0f}% {direction} so far this month "
            f"than in all of last month."
        )

    cats = by_category(qs.filter(date__gte=month_start(today, 2)))
    if cats:
        top = cats[0]
        notes.append(
            f"{top['label']} is your largest category over the last 3 months, "
            f"at {top['share']:.0f}% of spending."
        )

    # The category that grew most this month against its average of the 3 months before.
    this_start = month_start(today)
    base_start = month_start(today, 3)
    current = {
        r["category"]: r["total"]
        for r in qs.filter(date__gte=this_start).values("category").annotate(total=Sum("amount"))
    }
    baseline = {
        r["category"]: r["total"] / 3
        for r in qs.filter(date__gte=base_start, date__lt=this_start)
        .values("category")
        .annotate(total=Sum("amount"))
    }
    labels = dict(Expense.Category.choices)
    growth = [
        (pct_change(amount, baseline[cat]), cat)
        for cat, amount in current.items()
        if baseline.get(cat)
    ]
    growth = [g for g in growth if g[0] is not None and g[0] >= 20]
    if growth:
        pct, cat = max(growth)
        notes.append(
            f"{labels[cat]} is up {pct:.0f}% this month compared with your 3-month average."
        )

    biggest = qs.order_by("-amount").first()
    notes.append(
        f"Your largest single expense was ₹{biggest.amount:,.2f} "
        f"({biggest.get_category_display()}) on {biggest.date:%d %b %Y}."
    )
    return notes
