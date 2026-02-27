from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stores', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='menu',
            name='description',
            field=models.CharField(blank=True, max_length=200, verbose_name='설명'),
        ),
        migrations.AddField(
            model_name='menu',
            name='is_popular',
            field=models.BooleanField(default=False, verbose_name='인기 메뉴'),
        ),
        migrations.RemoveField(
            model_name='menu',
            name='category',
        ),
        migrations.AlterField(
            model_name='menu',
            name='price',
            field=models.PositiveIntegerField(verbose_name='가격'),
        ),
        migrations.AlterModelOptions(
            name='menu',
            options={'ordering': ['-is_popular', 'name'], 'verbose_name': '메뉴', 'verbose_name_plural': '메뉴'},
        ),
    ]
