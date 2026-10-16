import csv
from datetime import date

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import analytics
from .demo import ensure_demo_user
from .forms import ExpenseForm, FilterForm, SignUpForm
from .models import Expense


@login_required
def dashboard(request):
    qs = request.user.expenses.all()
    today = timezone.localdate()
    return render(request, "tracker/dashboard.html", {
        "today": today,
        "last_month": analytics.month_start(today, 1),
        "summary": analytics.summary(qs, today),
        "insights": analytics.insights(qs, today),
        "daily": analytics.daily_totals(qs, today),
        "trend": analytics.monthly_trend(qs, today),
        "categories": analytics.by_category(qs.filter(date__gte=analytics.month_start(today, 2))),
        "modes": analytics.by_payment_mode(qs),
        "recent": qs[:6],
        "category_choices": Expense.Category.choices,
        "mode_choices": Expense.PaymentMode.choices,
    })


def _filtered(request):
    qs = request.user.expenses.all()
    form = FilterForm(request.GET or None)
    if form.is_valid():
        if q := form.cleaned_data["q"]:
            qs = qs.filter(Q(description__icontains=q))
        if cat := form.cleaned_data["category"]:
            qs = qs.filter(category=cat)
        if month := form.cleaned_data["month"]:
            try:
                year, mon = (int(x) for x in month.split("-"))
                first = date(year, mon, 1)
                qs = qs.filter(date__gte=first, date__lt=analytics.month_start(first, -1))
            except ValueError:
                form.add_error("month", "Use the format YYYY-MM.")
    return qs, form


@login_required
def expense_list(request):
    qs, form = _filtered(request)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    # Group the page's rows by day, with a subtotal for each day.
    days = []
    for e in page.object_list:
        if not days or days[-1]["date"] != e.date:
            days.append({"date": e.date, "total": 0, "items": []})
        days[-1]["items"].append(e)
        days[-1]["total"] += e.amount
    return render(request, "tracker/expense_list.html", {
        "page": page,
        "days": days,
        "filtered": bool(params),
        "form": form,
        "total": qs.aggregate(t=Sum("amount"))["t"] or 0,
        "count": qs.count(),
        "querystring": params.urlencode(),
    })


@login_required
def expense_create(request):
    form = ExpenseForm(request.POST or None, initial={"date": timezone.localdate()})
    if form.is_valid():
        expense = form.save(commit=False)
        expense.user = request.user
        expense.save()
        messages.success(request, f"Added ₹{expense.amount:,.2f} · {expense.get_category_display()}.")
        if "add_another" in request.POST:
            return redirect("expense_create")
        if request.POST.get("next") == "dashboard":
            return redirect("dashboard")
        return redirect("expense_list")
    return render(request, "tracker/expense_form.html", {"form": form, "title": "Add expense"})


@login_required
def expense_update(request, pk):
    expense = get_object_or_404(request.user.expenses, pk=pk)
    form = ExpenseForm(request.POST or None, instance=expense)
    if form.is_valid():
        form.save()
        messages.success(request, "Expense updated.")
        return redirect("expense_list")
    return render(request, "tracker/expense_form.html", {
        "form": form, "title": "Edit expense", "expense": expense,
    })


@login_required
@require_POST
def expense_delete(request, pk):
    expense = get_object_or_404(request.user.expenses, pk=pk)
    expense.delete()
    messages.success(request, "Expense deleted.")
    return redirect("expense_list")


@login_required
def export_csv(request):
    qs, _ = _filtered(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'
    writer = csv.writer(response)
    writer.writerow(["date", "category", "description", "payment_mode", "amount"])
    for e in qs:
        writer.writerow([e.date.isoformat(), e.get_category_display(), e.description,
                         e.get_payment_mode_display(), e.amount])
    return response


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Account created. Add your first expense.")
        return redirect("expense_create")
    return render(request, "registration/signup.html", {"form": form})


@require_POST
def demo_login(request):
    user = ensure_demo_user()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.info(request, "You are using the shared demo account with sample data.")
    return redirect("dashboard")
