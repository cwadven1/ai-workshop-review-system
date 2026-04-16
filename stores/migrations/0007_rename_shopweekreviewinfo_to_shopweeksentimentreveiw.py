"""
ShopWeekReviewInfo → ShopWeekSentimentReveiw 모델명 변경
DB 테이블: stores_shopweekreviewinfo → stores_shopweeksentimentreveiw
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0006_shopweekreview_counts_shopweekreviewinfo_sentiment"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ShopWeekReviewInfo",
            new_name="ShopWeekSentimentReveiw",
        ),
    ]
