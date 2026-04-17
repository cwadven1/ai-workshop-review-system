from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0011_add_item_type_to_aiactionitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='aianalysisjob',
            name='job_type',
            field=models.CharField(default='all', max_length=20, verbose_name='분석 유형'),
        ),
    ]
