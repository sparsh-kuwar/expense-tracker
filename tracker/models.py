from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Expense(models.Model):
    class Category(models.TextChoices):
        FOOD = "food", "Food & Dining"
        TRANSPORT = "transport", "Transport"
        RENT = "rent", "Rent & Housing"
        UTILITIES = "utilities", "Utilities & Bills"
        SHOPPING = "shopping", "Shopping"
        HEALTH = "health", "Health"
        ENTERTAINMENT = "entertainment", "Entertainment"
        EDUCATION = "education", "Education"
        TRAVEL = "travel", "Travel"
        OTHER = "other", "Other"

    class PaymentMode(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        CARD = "card", "Card"
        NETBANKING = "netbanking", "Net banking"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses"
    )
    date = models.DateField()
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    payment_mode = models.CharField(
        max_length=20, choices=PaymentMode.choices, default=PaymentMode.UPI
    )
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [models.Index(fields=["user", "date"])]

    def __str__(self):
        return f"{self.date} {self.get_category_display()} {self.amount}"
