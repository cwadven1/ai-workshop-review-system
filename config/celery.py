import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('reviewtime')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# 매주 월요일 오전 9시 (Asia/Seoul 기준)
app.conf.beat_schedule = {
    'weekly-store-analysis': {
        'task': 'stores.tasks.run_weekly_analysis',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
    },
}
