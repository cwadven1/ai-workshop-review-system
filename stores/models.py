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


class ShopWeekReview(models.Model):
    shop = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="shop_week_reviews", verbose_name="가게")
    year = models.IntegerField("집계 연도")
    week_number = models.IntegerField("ISO 주차 번호")
    count = models.IntegerField("리뷰 수", default=0)
    average = models.FloatField("평균 별점", default=0.0)
    positive_count = models.IntegerField("긍정 리뷰 수", default=0)
    negative_count = models.IntegerField("부정 리뷰 수", default=0)
    neutral_count = models.IntegerField("중립 리뷰 수", default=0)
    summary = models.TextField("AI 요약", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "주차별 리뷰 집계"
        verbose_name_plural = "주차별 리뷰 집계"
        unique_together = [("shop", "year", "week_number")]
        indexes = [
            models.Index(fields=["shop", "year", "week_number"], name="idx_shop_year_week"),
        ]

    def __str__(self):
        return f"{self.shop.name} {self.year}-W{self.week_number:02d}"


class ShopWeekReviewSentiment(models.Model):
    SENTIMENT_CHOICES = [
        ("positive", "긍정"),
        ("negative", "부정"),
        ("neutral", "중립"),
    ]

    shop_week_review = models.ForeignKey(
        ShopWeekReview, on_delete=models.CASCADE, related_name="infos"
    )
    sentiment = models.CharField("감성", max_length=10, choices=SENTIMENT_CHOICES)
    content = models.TextField("AI 분석 내용", blank=True)
    created_at = models.DateTimeField("생성 시각", null=True)
    updated_at = models.DateTimeField("수정 시각", auto_now=True)

    class Meta:
        verbose_name = "주차별 리뷰 상세"
        verbose_name_plural = "주차별 리뷰 상세"

    def __str__(self):
        return f"{self.shop_week_review} ({self.get_sentiment_display()})"


class ShopRecentReview(models.Model):
    shop = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="shop_recent_reviews", verbose_name="가게")
    review_sample_start_date = models.DateField("샘플링 시작일")
    review_sample_end_date = models.DateField("샘플링 종료일")
    total_count = models.IntegerField("총 리뷰 수", default=0)
    positive_count = models.IntegerField("긍정 리뷰 수", default=0)
    negative_count = models.IntegerField("부정 리뷰 수", default=0)
    neutral_count = models.IntegerField("중립 리뷰 수", default=0)
    average = models.FloatField("평균 별점", default=0.0)
    summary = models.TextField("AI 전체 요약", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "최근 리뷰 집계"
        verbose_name_plural = "최근 리뷰 집계"
        indexes = [
            models.Index(fields=["shop", "created_at"], name="idx_shop_recent_created"),
        ]

    def __str__(self):
        return f"{self.shop.name} ({self.review_sample_start_date}~{self.review_sample_end_date})"


class ShopRecentReviewSentiment(models.Model):
    SENTIMENT_CHOICES = [
        ("positive", "긍정"),
        ("negative", "부정"),
        ("neutral", "중립"),
    ]

    shop_recent_review = models.ForeignKey(
        ShopRecentReview, on_delete=models.CASCADE, related_name="sentiments"
    )
    sentiment = models.CharField("감성", max_length=10, choices=SENTIMENT_CHOICES)
    content = models.TextField("AI 분석 내용", blank=True)
    created_at = models.DateTimeField("생성 시각", auto_now_add=True)

    class Meta:
        verbose_name = "최근 리뷰 감성 분석"
        verbose_name_plural = "최근 리뷰 감성 분석"

    def __str__(self):
        return f"{self.shop_recent_review} ({self.get_sentiment_display()})"


class Keyword(models.Model):
    SENTIMENT_CHOICES = [
        ("positive", "긍정"),
        ("negative", "부정"),
        ("neutral", "중립"),
    ]
    word = models.CharField("키워드", max_length=100, unique=True)
    sentiment = models.CharField("감성", max_length=10, choices=SENTIMENT_CHOICES, default="neutral")

    class Meta:
        verbose_name = "키워드"
        verbose_name_plural = "키워드"

    def __str__(self):
        return self.word


class AIAnalysisJob(models.Model):
    """LLM 분석 작업 이력 — 스케줄/수동 각 1회 호출 후 결과 저장"""

    TRIGGER_CHOICES = [
        ("schedule", "스케줄"),
        ("manual", "수동"),
    ]
    STATUS_CHOICES = [
        ("pending", "대기"),
        ("running", "실행 중"),
        ("completed", "완료"),
        ("failed", "실패"),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="ai_jobs", verbose_name="가게")
    status = models.CharField("상태", max_length=20, choices=STATUS_CHOICES, default="pending")
    triggered_by = models.CharField("트리거", max_length=20, choices=TRIGGER_CHOICES, default="schedule")
    source_week = models.ForeignKey(
        "ShopWeekReview", on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="기준 주차", related_name="ai_jobs"
    )
    raw_response = models.TextField("LLM 원본 응답", blank=True)
    error_message = models.TextField("오류 메시지", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField("완료 시각", null=True, blank=True)

    class Meta:
        verbose_name = "AI 분석 작업"
        verbose_name_plural = "AI 분석 작업"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.store.name} [{self.get_status_display()}] {self.created_at:%Y-%m-%d %H:%M}"


class AIActionItem(models.Model):
    """사장님 할일 목록 — LLM 분석에서 파생, 누적 관리"""

    LEVEL_CHOICES = [
        ("danger", "위험"),
        ("warning", "주의"),
        ("info", "정보"),
        ("success", "긍정"),
    ]
    PRIORITY_CHOICES = [
        ("high", "높음"),
        ("medium", "보통"),
        ("low", "낮음"),
    ]
    TYPE_CHOICES = [
        ("action", "개선 할일"),
        ("strength", "강점 인사이트"),
    ]
    STATUS_CHOICES = [
        ("open", "미처리"),
        ("in_progress", "처리 중"),
        ("completed", "완료"),
        ("dismissed", "기각"),
        ("confirmed", "확인됨"),
    ]

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="action_items", verbose_name="가게")
    source_job = models.ForeignKey(
        AIAnalysisJob, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="action_items", verbose_name="출처 작업"
    )
    title = models.CharField("제목", max_length=200)
    description = models.TextField("설명")
    action_detail = models.TextField("구체적 조치")
    level = models.CharField("레벨", max_length=20, choices=LEVEL_CHOICES, default="info")
    priority = models.CharField("우선순위", max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField("상태", max_length=20, choices=STATUS_CHOICES, default="open")
    completed_at = models.DateTimeField("완료 시각", null=True, blank=True)
    completed_note = models.TextField("완료 메모", blank=True)
    link_url = models.CharField("관련 링크 URL", max_length=500, blank=True)
    link_label = models.CharField("관련 링크 텍스트", max_length=100, blank=True)
    item_type = models.CharField("아이템 유형", max_length=20, choices=TYPE_CHOICES, default="action")
    week_year = models.IntegerField("집계 연도")
    week_number = models.IntegerField("집계 주차")
    is_ai_generated = models.BooleanField("AI 생성 여부", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI 액션 아이템"
        verbose_name_plural = "AI 액션 아이템"
        ordering = [
            models.Case(
                models.When(priority="high", then=0),
                models.When(priority="medium", then=1),
                models.When(priority="low", then=2),
                default=3,
                output_field=models.IntegerField(),
            ),
            "-created_at",
        ]
        indexes = [
            models.Index(fields=["store", "status"], name="idx_action_store_status"),
        ]

    def __str__(self):
        return f"{self.store.name} — {self.title} [{self.get_status_display()}]"


class ShopWeekReviewKeyword(models.Model):
    shop_week_review = models.ForeignKey(
        ShopWeekReview, on_delete=models.CASCADE, related_name="review_keywords"
    )
    keyword = models.ForeignKey(
        Keyword, on_delete=models.CASCADE, related_name="week_reviews"
    )
    count = models.IntegerField("출현 횟수", default=0)

    class Meta:
        verbose_name = "주차별 키워드"
        verbose_name_plural = "주차별 키워드"
        unique_together = [("shop_week_review", "keyword")]
        indexes = [
            models.Index(fields=["keyword"], name="idx_swrk_keyword"),
            models.Index(fields=["count"], name="idx_swrk_count"),
        ]

    def __str__(self):
        return f"{self.shop_week_review} - {self.keyword.word} ({self.count})"
