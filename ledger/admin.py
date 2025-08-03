from django.contrib import admin

from .models import Bank, Account


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    ordering = ["name"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["name"], "classes": ["wide"]}],
    ]


admin.site.register(Account)
