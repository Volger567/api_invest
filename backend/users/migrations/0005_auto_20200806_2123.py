# Generated by Django 3.0.8 on 2020-08-06 21:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0006_auto_20200806_2123'),
        ('users', '0004_auto_20200727_0140'),
    ]

    operations = [
        migrations.AlterField(
            model_name='currencyasset',
            name='currency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='market.CurrencyInstrument', verbose_name='Валюта'),
        ),
    ]
