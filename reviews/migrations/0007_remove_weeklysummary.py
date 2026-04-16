from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0006_review_updated_at'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WeeklySummary',
        ),
    ]
