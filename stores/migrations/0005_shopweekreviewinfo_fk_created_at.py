import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0004_shopweekreview_summary_info_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopweekreviewinfo',
            name='created_at',
            field=models.DateTimeField(null=True, verbose_name='생성 시각'),
        ),
        migrations.AlterField(
            model_name='shopweekreviewinfo',
            name='shop_week_review',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='infos',
                to='stores.shopweekreview',
            ),
        ),
    ]
