# Generated by Django 3.0.8 on 2020-08-18 12:41

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Currency',
            fields=[
                ('iso_code', models.CharField(max_length=3, primary_key=True, serialize=False, unique=True, verbose_name='Код')),
                ('abbreviation', models.CharField(max_length=16, verbose_name='Символ')),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='Название')),
            ],
            options={
                'verbose_name': 'Валюта',
                'verbose_name_plural': 'Валюты',
            },
        ),
        migrations.CreateModel(
            name='Operation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('PayIn', 'Пополнение счета'), ('PayOut', 'Вывод средств'), ('Buy', 'Покупка ценных бумаг'), ('BuyCard', 'Покупка ценных бумаг с банковской карты'), ('Sell', 'Продажа ценных бумаг'), ('Dividend', 'Получение дивидендов'), ('BrokerCommission', 'Комиссия брокера'), ('ServiceCommission', 'Комиссия за обслуживание'), ('MarginCommission', 'Комиссия за маржинальную торговлю'), ('Tax', 'Налог'), ('TaxBack', 'Налоговый вычет/корректировка налога'), ('TaxDividend', 'Налог на дивиденды'), ('Unknown', 'Неизвестен')], max_length=30, verbose_name='Тип')),
                ('date', models.DateTimeField(verbose_name='Дата')),
                ('is_margin_call', models.BooleanField(default=False)),
                ('payment', models.DecimalField(decimal_places=4, max_digits=20, verbose_name='Оплата')),
                ('quantity', models.PositiveIntegerField(default=0, verbose_name='Количество')),
                ('commission', models.DecimalField(decimal_places=4, default=0, max_digits=16, validators=[django.core.validators.MaxValueValidator(0, 'Коммиссия может быть только отрицательным число или 0')], verbose_name='Комиссия')),
                ('_id', models.CharField(default='-1', max_length=32, verbose_name='ID')),
                ('dividend_tax', models.IntegerField(default=0, validators=[django.core.validators.MaxValueValidator(0, 'Налог должен быть отрицательным числом или 0')], verbose_name='Налог')),
                ('dividend_tax_date', models.DateTimeField(null=True, verbose_name='Дата налога')),
            ],
            options={
                'verbose_name': 'Операция',
                'verbose_name_plural': 'Операции',
                'ordering': ('date',),
            },
        ),
        migrations.CreateModel(
            name='Share',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('value', models.DecimalField(decimal_places=8, max_digits=9, verbose_name='Доля')),
            ],
            options={
                'verbose_name': 'Доля в операции',
                'verbose_name_plural': 'Доли в операциях',
                'ordering': ['pk'],
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.CharField(max_length=32, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateTimeField(verbose_name='Дата')),
                ('quantity', models.PositiveIntegerField(verbose_name='Количество шт.')),
                ('price', models.DecimalField(decimal_places=4, max_digits=20, verbose_name='Цена/шт.')),
                ('operation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='operations.Operation', verbose_name='Операция')),
            ],
            options={
                'verbose_name': 'Транзакции',
                'verbose_name_plural': 'Транзакции',
            },
        ),
    ]
