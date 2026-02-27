from django.contrib import admin

from .models import Menu, Store


class MenuInline(admin.TabularInline):
    model = Menu
    extra = 1


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "avg_rating", "total_review_count")
    list_filter = ("category",)
    search_fields = ("name",)
    inlines = [MenuInline]


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("name", "store", "price", "is_popular")
    list_filter = ("is_popular",)
