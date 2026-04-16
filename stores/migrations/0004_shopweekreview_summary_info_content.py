from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0003_shopweekreview'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopweekreview',
            name='summary',
            field=models.TextField(blank=True, verbose_name='AI 요약'),
        ),
        migrations.RenameField(
            model_name='shopweekreviewinfo',
            old_name='summary',
            new_name='content',
        ),
        migrations.AlterField(
            model_name='shopweekreviewinfo',
            name='content',
            field=models.TextField(blank=True, verbose_name='AI 분석 내용'),
        ),
    ]
