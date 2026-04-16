from django.contrib import admin

from .models import MenuReview, Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("store", "rating", "sentiment", "week", "review_date", "is_deleted", "is_blinded")
    list_filter = ("sentiment", "week", "store", "is_deleted", "is_blinded")
    search_fields = ("content",)


@admin.register(MenuReview)
class MenuReviewAdmin(admin.ModelAdmin):
    list_display = ("menu", "review")
