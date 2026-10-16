from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import analytics
from .demo import DEMO_USERNAME, ensure_demo_user
from .models import Expense

User = get_user_model()


def add(user, day, amount, category="food", mode="upi", description=""):
    return Expense.objects.create(user=user, date=day, amount=Decimal(amount),
                                  category=category, payment_mode=mode,
                                  description=description)


class MonthStartTests(TestCase):
    def test_same_month(self):
        self.assertEqual(analytics.month_start(date(2026, 10, 15)), date(2026, 10, 1))

    def test_crosses_year_backwards(self):
        self.assertEqual(analytics.month_start(date(2026, 2, 10), 3), date(2025, 11, 1))

    def test_forwards(self):
        self.assertEqual(analytics.month_start(date(2026, 12, 5), -1), date(2027, 1, 1))


class AnalyticsTests(TestCase):
    today = date(2026, 10, 15)

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw-123456!")
        self.other = User.objects.create_user("bob", password="pw-123456!")
        add(self.user, date(2026, 10, 2), "300", "food", description="Groceries")
        add(self.user, date(2026, 10, 10), "700", "transport")
        add(self.user, date(2026, 9, 20), "500", "food")
        add(self.user, date(2026, 8, 5), "250.50", "shopping", "card")
        add(self.other, date(2026, 10, 3), "9999", "rent")
        self.qs = self.user.expenses.all()

    def test_summary(self):
        s = analytics.summary(self.qs, self.today)
        self.assertEqual(s["this_month"], Decimal("1000"))
        self.assertEqual(s["last_month"], Decimal("500"))
        self.assertAlmostEqual(s["change_pct"], 100.0)
        self.assertEqual(s["all_time"], Decimal("1750.50"))
        self.assertEqual(s["count"], 4)
        self.assertAlmostEqual(float(s["daily_average"]), 1000 / 15)

    def test_change_pct_none_without_last_month(self):
        self.assertIsNone(analytics.pct_change(Decimal("10"), Decimal("0")))

    def test_monthly_trend_fills_empty_months(self):
        trend = analytics.monthly_trend(self.qs, self.today, months=4)
        self.assertEqual([t["label"] for t in trend], ["Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026"])
        self.assertEqual([t["total"] for t in trend],
                         [0, Decimal("250.50"), Decimal("500"), Decimal("1000")])

    def test_by_category_sorted_with_shares(self):
        cats = analytics.by_category(self.qs)
        self.assertEqual([c["category"] for c in cats], ["food", "transport", "shopping"])
        self.assertAlmostEqual(sum(c["share"] for c in cats), 100.0)
        self.assertEqual(cats[0]["count"], 2)

    def test_insights_mention_change_and_largest(self):
        notes = analytics.insights(self.qs, self.today)
        self.assertTrue(any("100% more" in n for n in notes))
        self.assertTrue(any("₹700.00" in n for n in notes))

    def test_summary_compares_same_point_last_month(self):
        s = analytics.summary(self.qs, self.today)
        # Sep 20 is after Sep 15, so nothing counts "by this date" last month.
        self.assertEqual(s["last_month_to_date"], Decimal("0"))
        self.assertEqual(s["to_date_diff"], Decimal("1000"))
        self.assertAlmostEqual(float(s["projected"]), 1000 / 15 * 31)

    def test_same_point_clamps_to_short_month(self):
        add(self.user, date(2026, 2, 28), "40")
        s = analytics.summary(self.qs, date(2026, 3, 31))
        self.assertEqual(s["last_month_to_date"], Decimal("40"))

    def test_daily_totals_cover_whole_month(self):
        days = analytics.daily_totals(self.qs, self.today)
        self.assertEqual(len(days), 31)
        self.assertEqual(days[9]["total"], Decimal("700"))
        self.assertEqual(days[9]["height"], 100.0)
        self.assertTrue(days[14]["is_today"])
        self.assertTrue(days[20]["is_future"])

    def test_insights_empty_for_no_data(self):
        self.assertEqual(analytics.insights(Expense.objects.none(), self.today), [])


class ViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw-123456!")
        self.other = User.objects.create_user("bob", password="pw-123456!")
        self.client.force_login(self.user)

    def test_pages_require_login(self):
        self.client.logout()
        for name in ("dashboard", "expense_list", "expense_create", "export_csv"):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn(reverse("login"), resp["Location"])

    def test_empty_dashboard(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "No expenses yet")

    def test_dashboard_with_data(self):
        add(self.user, timezone.localdate(), "120")
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, "trendChart")
        self.assertContains(resp, "Insights")

    def test_quick_add_returns_to_dashboard(self):
        resp = self.client.post(reverse("expense_create"), {
            "date": timezone.localdate().isoformat(), "amount": "99",
            "category": "food", "payment_mode": "upi", "next": "dashboard",
        })
        self.assertRedirects(resp, reverse("dashboard"))

    def test_create_expense(self):
        resp = self.client.post(reverse("expense_create"), {
            "date": timezone.localdate().isoformat(), "amount": "450.75",
            "category": "food", "payment_mode": "upi", "description": "Lunch",
        })
        self.assertRedirects(resp, reverse("expense_list"))
        e = self.user.expenses.get()
        self.assertEqual(e.amount, Decimal("450.75"))

    def test_create_rejects_bad_input(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        for data in (
            {"date": tomorrow.isoformat(), "amount": "10", "category": "food", "payment_mode": "upi"},
            {"date": "2026-01-01", "amount": "-5", "category": "food", "payment_mode": "upi"},
            {"date": "2026-01-01", "amount": "5", "category": "nope", "payment_mode": "upi"},
        ):
            resp = self.client.post(reverse("expense_create"), data)
            self.assertEqual(resp.status_code, 200)
        self.assertFalse(Expense.objects.exists())

    def test_update_and_delete_own_expense(self):
        e = add(self.user, date(2026, 1, 1), "10")
        self.client.post(reverse("expense_update", args=[e.pk]), {
            "date": "2026-01-02", "amount": "20", "category": "health", "payment_mode": "cash",
        })
        e.refresh_from_db()
        self.assertEqual((e.amount, e.category), (Decimal("20"), "health"))
        self.client.post(reverse("expense_delete", args=[e.pk]))
        self.assertFalse(Expense.objects.filter(pk=e.pk).exists())

    def test_cannot_touch_other_users_expense(self):
        e = add(self.other, date(2026, 1, 1), "10")
        self.assertEqual(self.client.get(reverse("expense_update", args=[e.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("expense_delete", args=[e.pk])).status_code, 404)
        self.assertTrue(Expense.objects.filter(pk=e.pk).exists())

    def test_delete_requires_post(self):
        e = add(self.user, date(2026, 1, 1), "10")
        self.assertEqual(self.client.get(reverse("expense_delete", args=[e.pk])).status_code, 405)

    def test_list_filters(self):
        add(self.user, date(2026, 9, 5), "10", "food", description="Coffee")
        add(self.user, date(2026, 8, 5), "20", "transport", description="Taxi")
        add(self.other, date(2026, 9, 5), "30", "food", description="Coffee")
        url = reverse("expense_list")
        self.assertEqual(self.client.get(url).context["count"], 2)
        self.assertEqual(self.client.get(url, {"q": "coffee"}).context["count"], 1)
        self.assertEqual(self.client.get(url, {"category": "transport"}).context["count"], 1)
        self.assertEqual(self.client.get(url, {"month": "2026-09"}).context["count"], 1)
        resp = self.client.get(url, {"month": "garbage"})
        self.assertEqual(resp.status_code, 200)

    def test_export_csv_only_own_rows(self):
        add(self.user, date(2026, 9, 5), "10", description="Mine")
        add(self.other, date(2026, 9, 5), "30", description="Theirs")
        resp = self.client.get(reverse("export_csv"))
        body = resp.content.decode()
        self.assertEqual(resp["Content-Type"], "text/csv")
        self.assertIn("Mine", body)
        self.assertNotIn("Theirs", body)

    def test_signup_logs_in(self):
        self.client.logout()
        resp = self.client.post(reverse("signup"), {
            "username": "carol", "password1": "Str0ng-pass-99", "password2": "Str0ng-pass-99",
        })
        self.assertRedirects(resp, reverse("expense_create"))
        self.assertTrue(User.objects.filter(username="carol").exists())


class DemoTests(TestCase):
    def test_demo_login_seeds_current_data(self):
        resp = self.client.post(reverse("demo_login"))
        self.assertRedirects(resp, reverse("dashboard"))
        user = User.objects.get(username=DEMO_USERNAME)
        self.assertFalse(user.has_usable_password())
        self.assertGreater(user.expenses.count(), 100)
        this_month = analytics.month_start(timezone.localdate())
        self.assertTrue(user.expenses.filter(date__gte=this_month).exists())
        self.assertFalse(user.expenses.filter(date__gt=timezone.localdate()).exists())

    def test_ensure_demo_user_is_idempotent(self):
        first = ensure_demo_user().expenses.count()
        self.assertEqual(ensure_demo_user().expenses.count(), first)

    def test_stale_demo_data_is_regenerated(self):
        user = ensure_demo_user()
        user.expenses.all().delete()
        add(user, date(2020, 1, 1), "5")
        ensure_demo_user()
        self.assertFalse(user.expenses.filter(date=date(2020, 1, 1)).exists())

    def test_demo_login_requires_post(self):
        self.assertEqual(self.client.get(reverse("demo_login")).status_code, 405)
