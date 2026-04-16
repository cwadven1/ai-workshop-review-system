from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from stores.models import Menu, Store


class Review(models.Model):
    SENTIMENT_CHOICES = [
        ("positive", "긍정"),
        ("neutral", "중립"),
        ("negative", "부정"),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="reviews")
    rating = models.IntegerField(
        "평점",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    content = models.TextField("리뷰 내용")
    sentiment = models.CharField(
        "감정",
        max_length=10,
        choices=SENTIMENT_CHOICES,
        default="neutral",
    )
    sentiment_score = models.FloatField("감정 점수", default=0.0)
    keywords = models.JSONField("키워드", default=list, blank=True)
    week = models.IntegerField("주차", help_text="예: 14 (ISO 주차)", default=0)
    images = models.JSONField("리뷰 이미지", default=list, blank=True)
    review_date = models.DateField("리뷰 날짜")
    source = models.CharField("출처", max_length=50, default="yogiyo")
    is_deleted = models.BooleanField("삭제 여부", default=False)
    deleted_at = models.DateTimeField("삭제일시", null=True, blank=True)
    is_blinded = models.BooleanField("블라인드 여부", default=False)
    blinded_at = models.DateTimeField("블라인드일시", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰"
        indexes = [
            models.Index(fields=["store", "week", "created_at"], name="idx_store_week_created"),
        ]
        ordering = ["-review_date"]

    def __str__(self):
        return f"{self.store.name} - {self.rating}점 ({self.week}주차)"



class MenuReview(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="menu_reviews")
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="menu_reviews"
    )
    mentioned_text = models.TextField("언급 텍스트", blank=True)

    class Meta:
        verbose_name = "메뉴 리뷰"
        verbose_name_plural = "메뉴 리뷰"

    def __str__(self):
        return f"{self.menu.name} - Review#{self.review.pk}"
