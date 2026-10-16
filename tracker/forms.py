from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import Expense


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "amount", "category", "payment_mode", "description"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "amount": forms.NumberInput(attrs={
                "step": "0.01", "min": "0.01", "inputmode": "decimal", "placeholder": "0.00",
            }),
            "category": forms.RadioSelect,
            "payment_mode": forms.RadioSelect,
            "description": forms.TextInput(attrs={"placeholder": "e.g. Groceries at D-Mart"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Radio buttons, so no blank "choose one" option.
        self.fields["category"].choices = Expense.Category.choices

    def clean_date(self):
        date = self.cleaned_data["date"]
        if date > timezone.localdate():
            raise forms.ValidationError("Date cannot be in the future.")
        return date


class FilterForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    category = forms.ChoiceField(
        required=False, choices=[("", "All categories")] + Expense.Category.choices
    )
    month = forms.CharField(
        required=False, widget=forms.DateInput(attrs={"type": "month"})
    )


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username",)
