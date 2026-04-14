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
    year_month = models.CharField("연월", max_length=7, help_text="예: 2025-02", blank=True, default="")
    year_week = models.CharField("연주차", max_length=8, help_text="예: 2025-W14", blank=True, default="")
    images = models.JSONField("리뷰 이미지", default=list, blank=True)
    review_date = models.DateField("리뷰 날짜")
    source = models.CharField("출처", max_length=50, default="yogiyo")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "리뷰"
        verbose_name_plural = "리뷰"
        indexes = [
            models.Index(fields=["store", "year_month"], name="idx_store_year_month"),
            models.Index(fields=["store", "year_week"], name="idx_store_year_week"),
        ]
        ordering = ["-review_date"]

    def __str__(self):
        return f"{self.store.name} - {self.rating}점 ({self.year_week})"


class WeeklySummary(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="weekly_summaries"
    )
    year_week = models.CharField("연주차", max_length=8)
    summary = models.TextField("AI 요약", blank=True)
    highlights = models.JSONField("하이라이트", default=dict, blank=True)
    avg_rating = models.FloatField("주 평균 평점", default=0.0)
    review_count = models.IntegerField("주 리뷰 수", default=0)
    sentiment_distribution = models.JSONField(
        "감정 분포",
        default=dict,
        blank=True,
        help_text='예: {"positive": 60, "neutral": 25, "negative": 15}',
    )
    top_keywords = models.JSONField("상위 키워드", default=list, blank=True)
    rating_change = models.FloatField("평점 변화", default=0.0)
    generated_at = models.DateTimeField("생성일시", auto_now=True)

    class Meta:
        verbose_name = "주별 요약"
        verbose_name_plural = "주별 요약"
        unique_together = [("store", "year_week")]
        ordering = ["-year_week"]

    def __str__(self):
        return f"{self.store.name} - {self.year_week} 요약"


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
