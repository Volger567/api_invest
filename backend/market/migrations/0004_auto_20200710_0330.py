# Generated by Django 3.0.7 on 2020-07-10 00:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0003_auto_20200709_0137'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(condition=models.Q(_negated=True, secondary_id='-1'), fields=('secondary_id',), name='unique_sec_id'),
        ),
    ]