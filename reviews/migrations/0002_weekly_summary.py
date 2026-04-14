import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0001_initial'),
        ('stores', '0001_initial'),
    ]

    operations = [
        # Review에 year_week 필드 추가
        migrations.AddField(
            model_name='review',
            name='year_week',
            field=models.CharField(blank=True, default='', help_text='예: 2025-W14', max_length=8, verbose_name='연주차'),
        ),
        # year_month 기본값 처리
        migrations.AlterField(
            model_name='review',
            name='year_month',
            field=models.CharField(blank=True, default='', help_text='예: 2025-02', max_length=7, verbose_name='연월'),
        ),
        # year_week 인덱스 추가
        migrations.AddIndex(
            model_name='review',
            index=models.Index(fields=['store', 'year_week'], name='idx_store_year_week'),
        ),
        # WeeklySummary 모델 생성
        migrations.CreateModel(
            name='WeeklySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('year_week', models.CharField(max_length=8, verbose_name='연주차')),
                ('summary', models.TextField(blank=True, verbose_name='AI 요약')),
                ('highlights', models.JSONField(blank=True, default=dict, verbose_name='하이라이트')),
                ('avg_rating', models.FloatField(default=0.0, verbose_name='주 평균 평점')),
                ('review_count', models.IntegerField(default=0, verbose_name='주 리뷰 수')),
                ('sentiment_distribution', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='예: {"positive": 60, "neutral": 25, "negative": 15}',
                    verbose_name='감정 분포',
                )),
                ('top_keywords', models.JSONField(blank=True, default=list, verbose_name='상위 키워드')),
                ('rating_change', models.FloatField(default=0.0, verbose_name='평점 변화')),
                ('generated_at', models.DateTimeField(auto_now=True, verbose_name='생성일시')),
                ('store', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='weekly_summaries',
                    to='stores.store',
                )),
            ],
            options={
                'verbose_name': '주별 요약',
                'verbose_name_plural': '주별 요약',
                'ordering': ['-year_week'],
                'unique_together': {('store', 'year_week')},
            },
        ),
        # MonthlySummary 삭제
        migrations.DeleteModel(
            name='MonthlySummary',
        ),
    ]
