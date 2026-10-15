from django.contrib import admin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "category", "amount", "payment_mode", "description")
    list_filter = ("category", "payment_mode", "date")
    search_fields = ("description",)
