from django.contrib import admin

from .models import MenuReview, MonthlySummary, Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("store", "rating", "sentiment", "year_month", "review_date")
    list_filter = ("sentiment", "year_month", "store")
    search_fields = ("content",)


@admin.register(MonthlySummary)
class MonthlySummaryAdmin(admin.ModelAdmin):
    list_display = ("store", "year_month", "avg_rating", "review_count", "rating_change")
    list_filter = ("year_month", "store")


@admin.register(MenuReview)
class MenuReviewAdmin(admin.ModelAdmin):
    list_display = ("menu", "review")
