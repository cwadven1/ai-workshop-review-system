import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0002_menu_update'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShopWeekReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year', models.IntegerField(verbose_name='집계 연도')),
                ('week_number', models.IntegerField(verbose_name='ISO 주차 번호')),
                ('count', models.IntegerField(default=0, verbose_name='리뷰 수')),
                ('average', models.FloatField(default=0.0, verbose_name='평균 별점')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('shop', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='shop_week_reviews',
                    to='stores.store',
                    verbose_name='가게',
                )),
            ],
            options={
                'verbose_name': '주차별 리뷰 집계',
                'verbose_name_plural': '주차별 리뷰 집계',
                'unique_together': {('shop', 'year', 'week_number')},
            },
        ),
        migrations.AddIndex(
            model_name='shopweekreview',
            index=models.Index(fields=['shop', 'year', 'week_number'], name='idx_shop_year_week'),
        ),
        migrations.CreateModel(
            name='ShopWeekReviewInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('positive_count', models.IntegerField(default=0, verbose_name='긍정 리뷰 수')),
                ('negative_count', models.IntegerField(default=0, verbose_name='부정 리뷰 수')),
                ('neutral_count', models.IntegerField(default=0, verbose_name='중립 리뷰 수')),
                ('summary', models.TextField(blank=True, verbose_name='AI 요약')),
                ('shop_week_review', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='info',
                    to='stores.shopweekreview',
                )),
            ],
            options={
                'verbose_name': '주차별 리뷰 상세',
                'verbose_name_plural': '주차별 리뷰 상세',
            },
        ),
        migrations.CreateModel(
            name='Keyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('word', models.CharField(max_length=100, unique=True, verbose_name='키워드')),
                ('sentiment', models.CharField(
                    choices=[('positive', '긍정'), ('negative', '부정'), ('neutral', '중립')],
                    default='neutral',
                    max_length=10,
                    verbose_name='감성',
                )),
            ],
            options={
                'verbose_name': '키워드',
                'verbose_name_plural': '키워드',
            },
        ),
        migrations.CreateModel(
            name='ShopWeekReviewKeyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('count', models.IntegerField(default=0, verbose_name='출현 횟수')),
                ('keyword', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='week_reviews',
                    to='stores.keyword',
                )),
                ('shop_week_review', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='review_keywords',
                    to='stores.shopweekreview',
                )),
            ],
            options={
                'verbose_name': '주차별 키워드',
                'verbose_name_plural': '주차별 키워드',
                'unique_together': {('shop_week_review', 'keyword')},
            },
        ),
        migrations.AddIndex(
            model_name='shopweekreviewkeyword',
            index=models.Index(fields=['keyword'], name='idx_swrk_keyword'),
        ),
        migrations.AddIndex(
            model_name='shopweekreviewkeyword',
            index=models.Index(fields=['count'], name='idx_swrk_count'),
        ),
    ]
