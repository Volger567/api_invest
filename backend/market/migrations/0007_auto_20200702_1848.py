# Generated by Django 3.0.7 on 2020-07-02 15:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0006_auto_20200702_1741'),
    ]

    operations = [
        migrations.AddField(
            model_name='operation',
            name='figi',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='market.Stock', verbose_name='Ценная бумага'),
        ),
        migrations.AddField(
            model_name='operation',
            name='instrument_type',
            field=models.CharField(blank=True, max_length=32, verbose_name='Тип инструмента'),
        ),
        migrations.AddField(
            model_name='operation',
            name='quantity',
            field=models.PositiveIntegerField(default=0, verbose_name='Количество'),
        ),
    ]