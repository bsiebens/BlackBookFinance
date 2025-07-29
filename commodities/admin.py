from django.contrib import admin

from .models import Commodity

@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ["name", "code"]
    search_fields = ["name", "code"]
    fieldsets = [
        ["GENERAL INFORMATION", {"fields": ["name", "code"], "classes": ["wide"]}],
    ]