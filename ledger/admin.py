from django.conf import settings
from django.contrib import admin
from django.db.models import QuerySet
from django.utils.html import format_html
from moneyed.l10n import format_money

from .models import Bank, Account, Transaction, Posting


class PostingInline(admin.TabularInline):
    model = Posting
    extra = 0
    readonly_fields = ["foreign_amount", "foreign_commodity"]


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    ordering = ["name"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["name"], "classes": ["wide"]}],
    ]


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["indented_name", "type", "bank", "default_currency", "display_balance", "created", "updated"]
    list_filter = ["type", "bank", "default_currency"]
    search_fields = ["name"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["parent", "name", "type", "bank", "default_currency"], "classes": ["wide"]}],
    ]

    def get_queryset(self, request) -> QuerySet:
        return super().get_queryset(request).with_tree_fields().order_siblings_by("name")

    def display_balance(self, obj) -> str:
        """Display balance as currency amount."""
        return format_money(obj.balance, locale=getattr(settings, "LANGUAGE_CODE", "en_US").replace("-", "_"))

    display_balance.short_description = "Balance"

    def indented_name(self, obj) -> str:
        """Display account name with indentation and tree indicators based on tree depth."""
        # Calculate indentation (reduce spacing since we're adding visual elements)
        indent = "&nbsp;" * 2 * obj.tree_depth

        # Check if this node has children by looking for child accounts
        has_children = Account.objects.filter(parent=obj).exists()

        # Tree structure visual indicators
        tree_chars = ""
        if obj.tree_depth > 0:
            # Add tree branch characters for better hierarchy visualization
            tree_chars = "├─ " if has_children else "└─ "

        return format_html(f'<span style="font-family: monospace;">{indent}{tree_chars}</span>' f"<strong>{obj.name}</strong>")

    indented_name.short_description = "Name"
    indented_name.admin_order_field = "name"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["description", "date", "display_balance", "created", "updated"]
    search_fields = ["description"]
    date_hierarchy = "date"
    ordering = ["-date"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["date", "description", "amounts"], "classes": ["wide"]}],
    ]
    inlines = [PostingInline]

    def display_balance(self, obj) -> str:
        """Display balance as currency amount."""
        return format_money(obj.balance, locale=getattr(settings, "LANGUAGE_CODE", "en_US").replace("-", "_"))

    display_balance.short_description = "Balance"
