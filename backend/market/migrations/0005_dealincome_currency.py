# Generated by Django 3.0.8 on 2020-08-20 18:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('operations', '0003_operation_co_owners'),
        ('market', '0004_auto_20200818_2222'),
    ]

    operations = [
        migrations.AddField(
            model_name='dealincome',
            name='currency',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='operations.Currency', verbose_name='Валюта'),
            preserve_default=False,
        ),
    ]
