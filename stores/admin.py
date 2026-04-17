from django.contrib import admin

from .models import Keyword, Menu, ShopWeekReview, ShopWeekReviewSentiment, ShopWeekReviewKeyword, Store


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


@admin.register(ShopWeekReview)
class ShopWeekReviewAdmin(admin.ModelAdmin):
    list_display = ("shop", "year", "week_number", "count", "average", "updated_at")
    list_filter = ("year", "shop")
    search_fields = ("shop__name",)


@admin.register(ShopWeekReviewSentiment)
class ShopWeekReviewSentimentAdmin(admin.ModelAdmin):
    list_display = ("shop_week_review", "sentiment", "created_at", "updated_at")


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("word", "sentiment")
    list_filter = ("sentiment",)
    search_fields = ("word",)


@admin.register(ShopWeekReviewKeyword)
class ShopWeekReviewKeywordAdmin(admin.ModelAdmin):
    list_display = ("shop_week_review", "keyword", "count")
    list_filter = ("keyword__sentiment",)
