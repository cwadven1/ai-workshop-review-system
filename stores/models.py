from django.db import models


class Store(models.Model):
    CATEGORY_CHOICES = [
        ("korean", "한식"),
        ("japanese", "일식"),
        ("chinese", "중식"),
        ("western", "양식"),
        ("chicken", "치킨"),
        ("pizza", "피자"),
        ("cafe", "카페"),
        ("etc", "기타"),
    ]

    name = models.CharField("가게명", max_length=100)
    category = models.CharField("카테고리", max_length=20, choices=CATEGORY_CHOICES)
    address = models.CharField("주소", max_length=200, blank=True)
    phone = models.CharField("전화번호", max_length=20, blank=True)
    image_url = models.URLField("이미지 URL", blank=True)
    avg_rating = models.FloatField("평균 평점", default=0.0)
    total_review_count = models.IntegerField("총 리뷰 수", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "가게"
        verbose_name_plural = "가게"

    def __str__(self):
        return self.name

    def get_category_display_name(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)


class Menu(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="menus")
    name = models.CharField("메뉴명", max_length=100)
    price = models.PositiveIntegerField("가격")
    description = models.CharField("설명", max_length=200, blank=True)
    is_popular = models.BooleanField("인기 메뉴", default=False)

    class Meta:
        ordering = ["-is_popular", "name"]
        verbose_name = "메뉴"
        verbose_name_plural = "메뉴"

    def __str__(self):
        return f"{self.store.name} - {self.name}"
