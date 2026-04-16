from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0007_rename_shopweekreviewinfo_to_shopweeksentimentreveiw"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShopRecentReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_sample_start_date", models.DateField(verbose_name="샘플링 시작일")),
                ("review_sample_end_date", models.DateField(verbose_name="샘플링 종료일")),
                ("total_count", models.IntegerField(default=0, verbose_name="총 리뷰 수")),
                ("positive_count", models.IntegerField(default=0, verbose_name="긍정 리뷰 수")),
                ("negative_count", models.IntegerField(default=0, verbose_name="부정 리뷰 수")),
                ("neutral_count", models.IntegerField(default=0, verbose_name="중립 리뷰 수")),
                ("average", models.FloatField(default=0.0, verbose_name="평균 별점")),
                ("summary", models.TextField(blank=True, verbose_name="AI 전체 요약")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "shop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shop_recent_reviews",
                        to="stores.store",
                        verbose_name="가게",
                    ),
                ),
            ],
            options={
                "verbose_name": "최근 리뷰 집계",
                "verbose_name_plural": "최근 리뷰 집계",
            },
        ),
        migrations.AddIndex(
            model_name="shoprecentreview",
            index=models.Index(fields=["shop", "created_at"], name="idx_shop_recent_created"),
        ),
        migrations.CreateModel(
            name="ShopRecentReviewSentiment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "sentiment",
                    models.CharField(
                        choices=[("positive", "긍정"), ("negative", "부정"), ("neutral", "중립")],
                        max_length=10,
                        verbose_name="감성",
                    ),
                ),
                ("content", models.TextField(blank=True, verbose_name="AI 분석 내용")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="생성 시각")),
                (
                    "shop_recent_review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sentiments",
                        to="stores.shoprecentreview",
                    ),
                ),
            ],
            options={
                "verbose_name": "최근 리뷰 감성 분석",
                "verbose_name_plural": "최근 리뷰 감성 분석",
            },
        ),
    ]
