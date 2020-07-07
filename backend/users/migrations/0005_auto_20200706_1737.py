# Generated by Django 3.0.7 on 2020-07-06 14:37

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_currencyasset_investment_account'),
    ]

    operations = [
        migrations.AlterField(
            model_name='currencyasset',
            name='investment_account',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='currency_assets', to='users.InvestmentAccount', verbose_name='Инвестиционный счет'),
        ),
    ]