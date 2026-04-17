from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("stores", "0008_shoprecentreview_shoprecentreviewsentiment"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="ShopWeekSentimentReveiw",
            new_name="ShopWeekReviewSentiment",
        ),
    ]
