from django.contrib import admin

from .models import MenuReview, Review, WeeklySummary


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("store", "rating", "sentiment", "year_week", "review_date")
    list_filter = ("sentiment", "year_week", "store")
    search_fields = ("content",)


@admin.register(WeeklySummary)
class WeeklySummaryAdmin(admin.ModelAdmin):
    list_display = ("store", "year_week", "avg_rating", "review_count", "rating_change")
    list_filter = ("year_week", "store")


@admin.register(MenuReview)
class MenuReviewAdmin(admin.ModelAdmin):
    list_display = ("menu", "review")
