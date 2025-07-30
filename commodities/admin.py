from django.contrib import admin

from .models import Commodity, Price


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "commodity_type", "backend", "auto_update"]
    list_filter = ["commodity_type", "backend", "auto_update"]
    search_fields = ["name", "code"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["name", "code", "commodity_type"], "classes": ["wide"]}],
        ["UPDATE INFORMATION", {"fields": ["backend", "auto_update"], "classes": ["wide"]}],
        ["WEBSITE INFORMATION", {"fields": ["website", "xpath_selector"], "classes": ["wide"]}],
    ]


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ["date", "commodity", "price", "unit", "created", "updated"]
    date_hierarchy = "date"
    ordering = ["-date"]
    list_filter = ["commodity", "unit"]
    search_fields = ["commodity__name", "commodity__code", "unit__name", "unit__code"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["date", "commodity", "price", "unit"], "classes": ["wide"]}],
    ]
