from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0002_weekly_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='review',
            name='images',
            field=models.JSONField(blank=True, default=list, verbose_name='리뷰 이미지'),
        ),
    ]
