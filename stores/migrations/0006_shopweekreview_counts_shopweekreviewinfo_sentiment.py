"""
ShopWeekReview에 positive_count/negative_count/neutral_count 이동,
ShopWeekSentimentReveiw에 sentiment + updated_at 추가, 기존 count 필드 제거.

데이터 이전 순서:
1. ShopWeekReview에 count 필드 추가 (default=0)
2. ShopWeekSentimentReveiw에 sentiment, updated_at 추가
3. RunPython: 기존 infos의 count를 ShopWeekReview로 백필
4. ShopWeekSentimentReveiw에서 count 필드 제거
"""
from django.db import migrations, models


def backfill_swr_counts(apps, schema_editor):
    ShopWeekReview = apps.get_model("stores", "ShopWeekReview")
    for swr in ShopWeekReview.objects.all():
        latest_info = swr.infos.order_by("-created_at").first()
        if latest_info:
            swr.positive_count = latest_info.positive_count
            swr.negative_count = latest_info.negative_count
            swr.neutral_count = latest_info.neutral_count
            swr.save(update_fields=["positive_count", "negative_count", "neutral_count"])


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0005_shopweekreviewinfo_fk_created_at"),
    ]

    operations = [
        # 1. ShopWeekReview에 count 필드 추가
        migrations.AddField(
            model_name="shopweekreview",
            name="positive_count",
            field=models.IntegerField("긍정 리뷰 수", default=0),
        ),
        migrations.AddField(
            model_name="shopweekreview",
            name="negative_count",
            field=models.IntegerField("부정 리뷰 수", default=0),
        ),
        migrations.AddField(
            model_name="shopweekreview",
            name="neutral_count",
            field=models.IntegerField("중립 리뷰 수", default=0),
        ),
        # 2. ShopWeekSentimentReveiw에 sentiment, updated_at 추가
        migrations.AddField(
            model_name="shopweekreviewinfo",
            name="sentiment",
            field=models.CharField(
                "감성",
                max_length=10,
                choices=[("positive", "긍정"), ("negative", "부정"), ("neutral", "중립")],
                default="neutral",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shopweekreviewinfo",
            name="updated_at",
            field=models.DateTimeField("수정 시각", auto_now=True),
        ),
        # 3. 기존 info count → ShopWeekReview 백필
        migrations.RunPython(backfill_swr_counts, migrations.RunPython.noop),
        # 4. ShopWeekSentimentReveiw에서 count 필드 제거
        migrations.RemoveField(
            model_name="shopweekreviewinfo",
            name="positive_count",
        ),
        migrations.RemoveField(
            model_name="shopweekreviewinfo",
            name="negative_count",
        ),
        migrations.RemoveField(
            model_name="shopweekreviewinfo",
            name="neutral_count",
        ),
    ]
